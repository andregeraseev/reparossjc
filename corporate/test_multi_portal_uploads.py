import hashlib
import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Organization, OrganizationProvider, PartnerMembership, PortalChannel, ServiceProvider, ServiceRequest


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MultiPortalUploadTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media.cleanup)

        self.organization = Organization.objects.create(id="org_amil", slug="amil", name="Amil", display_name="Amil")
        self.provider = ServiceProvider.objects.create(
            id="provider_reparos",
            slug="reparos-sjc",
            name="Reparos SJC",
            display_name="Reparos SJC",
            workspace_id="ws_reparos",
            operator_token_hash=hashlib.sha256(b"provider-token-123456789").hexdigest(),
        )
        OrganizationProvider.objects.create(organization=self.organization, provider=self.provider, active=True, is_default=True)
        self.maintenance = PortalChannel.objects.create(
            id="PC_MAINT",
            organization=self.organization,
            slug="manutencao",
            display_name="Amil Manutenção",
            default_category="Manutenção",
            default_provider=self.provider,
        )
        self.legal = PortalChannel.objects.create(
            id="PC_LEGAL",
            organization=self.organization,
            slug="juridico",
            display_name="Amil Jurídico",
            default_category="Jurídico",
            default_provider=self.provider,
        )
        self.user = get_user_model().objects.create_user(username="amil-manager", password="test-pass-123")
        PartnerMembership.objects.create(user=self.user, organization=self.organization, role="manager")
        self.client.login(username="amil-manager", password="test-pass-123")

    def image(self, name="foto.png"):
        return SimpleUploadedFile(name, PNG_1X1, content_type="image/png")

    def create_request(self, *, channel=None, external="AMIL-001", image=True):
        channel = channel or self.maintenance
        data = {
            "organization_slug": self.organization.slug,
            "portal_channel_id": channel.id,
            "provider_id": self.provider.id,
            "external_request_id": external,
            "location": "Flat 03",
            "description": "Avaliar vazamento",
            "images": [self.image()] if image else [],
        }
        return self.client.post(reverse("corporate:portal_create"), data)

    def auth(self):
        return {"HTTP_X_WORKSPACE_ID": "ws_reparos", "HTTP_AUTHORIZATION": "Bearer provider-token-123456789"}

    def test_each_channel_has_an_independent_portal_and_request_list(self):
        self.create_request(channel=self.maintenance, external="AMIL-MAN")
        self.create_request(channel=self.legal, external="AMIL-JUR", image=False)

        maintenance = self.client.get(reverse("corporate:portal_channel", args=["amil", "manutencao"]))
        self.assertContains(maintenance, "Amil Manutenção")
        self.assertContains(maintenance, "AMIL-MAN")
        self.assertNotContains(maintenance, "AMIL-JUR")

        legal = self.client.get(reverse("corporate:portal_channel", args=["amil", "juridico"]))
        self.assertContains(legal, "AMIL-JUR")
        self.assertNotContains(legal, "AMIL-MAN")

    def test_uploaded_image_is_private_and_reaches_only_assigned_provider(self):
        response = self.create_request()
        self.assertEqual(response.status_code, 302)
        row = ServiceRequest.objects.get(external_request_id="AMIL-001")
        attachment = row.image_attachments.get()
        self.assertEqual(row.portal_channel, self.maintenance)
        self.assertEqual(attachment.content_type, "image/png")
        self.assertNotIn("foto.png", attachment.file.name)

        api = self.client.get(reverse("corporate:operator_requests"), **self.auth())
        payload = api.json()["requests"][0]["serviceRequest"]
        metadata = payload["attachments"][0]
        self.assertEqual(metadata["id"], attachment.id)
        self.assertTrue(metadata["downloadPath"].endswith(attachment.id))
        self.assertNotIn("checksum", str(metadata).lower())
        self.assertNotIn(self.media.name, str(metadata))

        downloaded = self.client.get(reverse("corporate:operator_attachment", args=[attachment.id]), **self.auth())
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded["Content-Type"], "image/png")
        self.assertEqual(downloaded["Cache-Control"], "private, no-store")
        preflight = self.client.options(
            reverse("corporate:operator_attachment", args=[attachment.id]),
            HTTP_ORIGIN="null",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,x-workspace-id",
        )
        self.assertEqual(preflight.status_code, 204)

        wrong_workspace = self.client.get(
            reverse("corporate:operator_attachment", args=[attachment.id]),
            HTTP_X_WORKSPACE_ID="ws_other",
            HTTP_AUTHORIZATION="Bearer provider-token-123456789",
        )
        self.assertEqual(wrong_workspace.status_code, 401)

    def test_unrelated_portal_user_cannot_read_attachment(self):
        self.create_request()
        attachment = ServiceRequest.objects.get(external_request_id="AMIL-001").image_attachments.get()
        other_org = Organization.objects.create(id="org_other", slug="other", name="Other", display_name="Other")
        other = get_user_model().objects.create_user(username="other", password="test-pass-123")
        PartnerMembership.objects.create(user=other, organization=other_org, role="manager")
        self.client.login(username="other", password="test-pass-123")
        self.assertEqual(self.client.get(reverse("corporate:portal_attachment", args=[attachment.id])).status_code, 404)

    def test_invalid_upload_is_rejected_without_creating_request(self):
        bad = SimpleUploadedFile("not-image.jpg", b"not an image", content_type="image/jpeg")
        response = self.client.post(
            reverse("corporate:portal_create"),
            {
                "organization_slug": "amil",
                "portal_channel_id": self.maintenance.id,
                "provider_id": self.provider.id,
                "external_request_id": "AMIL-BAD",
                "location": "Flat 01",
                "description": "Teste",
                "images": [bad],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceRequest.objects.filter(external_request_id="AMIL-BAD").exists())

    def test_more_than_eight_images_is_rejected(self):
        response = self.client.post(
            reverse("corporate:portal_create"),
            {
                "organization_slug": "amil",
                "portal_channel_id": self.maintenance.id,
                "provider_id": self.provider.id,
                "external_request_id": "AMIL-MANY",
                "location": "Flat 01",
                "description": "Teste",
                "images": [self.image(f"foto-{i}.png") for i in range(9)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceRequest.objects.filter(external_request_id="AMIL-MANY").exists())

    def test_forged_channel_from_other_organization_is_rejected(self):
        other = Organization.objects.create(id="org_other_channel", slug="other-channel", name="Other", display_name="Other")
        forged = PortalChannel.objects.create(id="PC_OTHER", organization=other, slug="juridico", display_name="Other Jurídico")
        response = self.client.post(
            reverse("corporate:portal_create"),
            {
                "organization_slug": "amil",
                "portal_channel_id": forged.id,
                "provider_id": self.provider.id,
                "external_request_id": "AMIL-FORGED",
                "location": "Flat 01",
                "description": "Teste",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceRequest.objects.filter(external_request_id="AMIL-FORGED").exists())

    def test_viewer_role_cannot_create_or_approve(self):
        viewer = get_user_model().objects.create_user(username="viewer", password="test-pass-123")
        PartnerMembership.objects.create(user=viewer, organization=self.organization, role="viewer")
        self.client.login(username="viewer", password="test-pass-123")
        response = self.client.post(
            reverse("corporate:portal_create"),
            {"organization_slug": "amil", "portal_channel_id": self.maintenance.id, "provider_id": self.provider.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_management_command_registers_new_company_portal_and_existing_user(self):
        user = get_user_model().objects.create_user(username="top-manager", password="test-pass-123")
        output = io.StringIO()
        call_command(
            "create_corporate_portal",
            organization_slug="top-moveis",
            organization_name="Top Móveis",
            portal_slug="manutencao",
            portal_name="Top Móveis Manutenção",
            category="Móveis",
            provider_slug="reparos-sjc",
            username=user.username,
            stdout=output,
        )
        channel = PortalChannel.objects.get(organization__slug="top-moveis", slug="manutencao")
        self.assertEqual(channel.display_name, "Top Móveis Manutenção")
        self.assertEqual(channel.default_provider, self.provider)
        self.assertTrue(PartnerMembership.objects.filter(user=user, organization=channel.organization, role="manager").exists())
        self.assertIn("/corporativo/p/top-moveis/manutencao/", output.getvalue())
