import secrets
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    AvailabilitySnapshot,
    Organization,
    OrganizationProvider,
    PartnerMembership,
    PortalChannel,
    PortalChannelMembership,
    PortalPerson,
    ServiceProvider,
    ServiceRequest,
)
from .services import contract_for, upsert_from_contract


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


class PortalV1830FullRegressionTests(TestCase):
    """One deterministic regression for the four production portal shapes.

    This intentionally stays inside Django's test database/filesystem. It does
    not need production passwords, does not touch the deployed SQLite database,
    and does not perform any external deploy or mutation.
    """

    def setUp(self):
        self.login_password = secrets.token_urlsafe(32)
        self.media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media.cleanup)

        self.provider = ServiceProvider.objects.create(
            id="provider_regression_v1830",
            slug="reparos-sjc-regression-v1830",
            name="Reparos SJC QA",
            display_name="Reparos SJC QA",
            workspace_id="ws-v1830-full-regression",
            active=True,
        )
        self.cris_org = Organization.objects.create(
            id="org_cris_regression",
            slug="cris-teste",
            name="Cris Teste",
            display_name="Cris Teste",
            demo=False,
            active=True,
        )
        self.amil_org = Organization.objects.create(
            id="org_amil_regression",
            slug="amil",
            name="Amil",
            display_name="Amil",
            demo=False,
            active=True,
        )
        for org in (self.cris_org, self.amil_org):
            OrganizationProvider.objects.create(
                organization=org,
                provider=self.provider,
                active=True,
                is_default=True,
            )

        channel_specs = (
            ("cris", self.cris_org, "portal_cris_teste", "teste", "Cris Teste", "Teste", 10),
            ("juridico", self.amil_org, "portal_amil_juridico", "juridico", "Amil Jurídico", "Jurídico", 20),
            ("manutencao", self.amil_org, "portal_amil_manutencao", "manutencao", "Amil Manutenção", "Manutenção", 30),
            ("distrato", self.amil_org, "portal_amil_distrato", "distrato", "Amil Distrato", "Distrato", 40),
        )
        User = get_user_model()
        self.portals = {}
        for key, org, username, slug, display_name, category, order in channel_specs:
            channel = PortalChannel.objects.create(
                id=f"portal_reg_{key}",
                organization=org,
                slug=slug,
                display_name=display_name,
                default_category=category,
                default_provider=self.provider,
                active=True,
                sort_order=order,
            )
            user = User.objects.create_user(username=username, password=self.login_password)
            PartnerMembership.objects.create(user=user, organization=org, role="manager", active=True)
            PortalChannelMembership.objects.create(
                user=user,
                portal_channel=channel,
                role="manager",
                active=True,
            )
            person = PortalPerson.objects.create(
                portal_channel=channel,
                name=f"Pessoa QA {key}",
                role_label="Responsável QA",
                phone=f"11000000{order}",
                email=f"{key}@example.test",
            )
            row = ServiceRequest.objects.create(
                id=f"SRREG{order}",
                external_request_id=f"REG-{key.upper()}-001",
                organization=org,
                portal_channel=channel,
                provider=self.provider,
                workspace_id=self.provider.workspace_id,
                location={"label": f"Local QA {key}", "address": "Endereço sintético de QA"},
                requester={"name": person.name, "personId": person.id},
                category=category,
                description=f"Descrição exclusiva QA {key}",
                status="new",
            )
            self.portals[key] = {
                "org": org,
                "user": user,
                "username": username,
                "channel": channel,
                "person": person,
                "row": row,
            }

    def portal_url(self, key):
        spec = self.portals[key]
        return reverse(
            "corporate:portal_channel",
            args=[spec["org"].slug, spec["channel"].slug],
        )

    def force_portal(self, key):
        self.client.force_login(self.portals[key]["user"])

    def image(self, key):
        return SimpleUploadedFile(f"qa-{key}.png", PNG_1X1, content_type="image/png")

    def test_logout_then_login_switches_identity_and_scope(self):
        self.client.logout()
        login_url = reverse("corporate:login")

        first = self.client.post(
            login_url,
            {"username": self.portals["cris"]["username"], "password": self.login_password},
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(
            str(self.client.session.get("_auth_user_id")),
            str(self.portals["cris"]["user"].pk),
        )
        self.assertEqual(self.client.get(self.portal_url("cris")).status_code, 200)

        confirm = self.client.get(reverse("corporate:logout"))
        self.assertEqual(confirm.status_code, 200)
        self.assertContains(confirm, "Sair do portal?")
        self.assertIn("_auth_user_id", self.client.session)

        logged_out = self.client.post(reverse("corporate:logout"))
        self.assertEqual(logged_out.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

        second = self.client.post(
            login_url,
            {"username": self.portals["juridico"]["username"], "password": self.login_password},
        )
        self.assertEqual(second.status_code, 302)
        self.assertEqual(
            str(self.client.session.get("_auth_user_id")),
            str(self.portals["juridico"]["user"].pk),
        )
        self.assertEqual(self.client.get(self.portal_url("juridico")).status_code, 200)
        self.assertEqual(self.client.get(self.portal_url("manutencao")).status_code, 404)
        self.assertEqual(self.client.get(self.portal_url("cris")).status_code, 403)

    def test_all_four_pages_people_and_api_are_strictly_isolated(self):
        keys = tuple(self.portals)
        for key in keys:
            self.force_portal(key)
            response = self.client.get(self.portal_url(key))
            self.assertEqual(response.status_code, 200, key)
            self.assertContains(response, self.portals[key]["row"].description)
            self.assertContains(response, self.portals[key]["person"].name)
            for other in keys:
                if other == key:
                    continue
                self.assertNotContains(response, self.portals[other]["row"].description)
                self.assertNotContains(response, self.portals[other]["person"].name)

            api = self.client.get(reverse("corporate:portal_requests_api"))
            self.assertEqual(api.status_code, 200, key)
            visible = {item["serviceRequest"]["id"] for item in api.json()["requests"]}
            self.assertEqual(visible, {self.portals[key]["row"].id}, key)

        self.force_portal("juridico")
        self.assertEqual(self.client.get(self.portal_url("manutencao")).status_code, 404)
        self.assertEqual(self.client.get(self.portal_url("distrato")).status_code, 404)
        self.assertEqual(self.client.get(self.portal_url("cris")).status_code, 403)

        self.force_portal("cris")
        self.assertEqual(self.client.get(self.portal_url("juridico")).status_code, 403)

    def test_private_images_work_for_owner_and_404_for_other_portals(self):
        keys = tuple(self.portals)
        for index, key in enumerate(keys):
            spec = self.portals[key]
            self.force_portal(key)
            external = f"IMG-{key.upper()}-001"
            created = self.client.post(
                reverse("corporate:portal_create"),
                {
                    "organization_slug": spec["org"].slug,
                    "portal_channel_id": spec["channel"].id,
                    "provider_id": self.provider.id,
                    "portal_person_id": spec["person"].id,
                    "external_request_id": external,
                    "location": f"Local imagem {key}",
                    "description": f"Chamado imagem {key}",
                    "images": [self.image(key)],
                },
            )
            self.assertEqual(created.status_code, 302, key)
            row = ServiceRequest.objects.get(organization=spec["org"], external_request_id=external)
            attachment = row.image_attachments.get()

            own = self.client.get(reverse("corporate:portal_attachment", args=[attachment.id]))
            self.assertEqual(own.status_code, 200, key)
            self.assertEqual(own["Content-Type"], "image/png")
            self.assertEqual(own["Cache-Control"], "private, no-store")
            own.close()

            foreign_key = keys[(index + 1) % len(keys)]
            self.force_portal(foreign_key)
            denied = self.client.get(reverse("corporate:portal_attachment", args=[attachment.id]))
            self.assertEqual(denied.status_code, 404, f"{key} -> {foreign_key}")

    def test_real_quote_approval_offer_and_schedule_succeeds_for_all_four(self):
        future_dates = {
            "cris": "2099-09-01",
            "juridico": "2099-09-02",
            "manutencao": "2099-09-03",
            "distrato": "2099-09-04",
        }
        keys = tuple(self.portals)

        for index, key in enumerate(keys):
            spec = self.portals[key]
            row = ServiceRequest.objects.get(pk=spec["row"].pk)

            payload = contract_for(row)
            payload["serviceRequest"]["status"] = "quote_sent"
            payload["quote"] = {
                "id": f"Q-{key}",
                "status": "Enviado",
                "total": 500,
                "discount": 0,
                "execution": "",
                "payment": "",
                "validity": "",
                "warranty": "",
                "items": [{"name": f"Serviço QA {key}", "qty": 1, "total": 500}],
            }
            row = upsert_from_contract(
                payload,
                provider=self.provider,
                workspace_id=self.provider.workspace_id,
            )
            row.refresh_from_db()
            self.assertEqual(row.status, "quote_sent", key)
            self.assertEqual(row.quote["items"][0]["total"], 500)
            self.assertEqual(row.quote["items"][0]["price"], 500)

            self.force_portal(key)
            rendered = self.client.get(self.portal_url(key))
            self.assertEqual(rendered.status_code, 200, key)
            self.assertContains(rendered, f"Serviço QA {key}")

            approved = self.client.post(reverse("corporate:portal_approve", args=[row.id]))
            self.assertEqual(approved.status_code, 302, key)
            row.refresh_from_db()
            self.assertEqual(row.client_decision, "approved", key)
            self.assertEqual(row.status, "quote_approved", key)

            window = {
                "sourceId": f"WINDOW-{index + 1}",
                "date": future_dates[key],
                "start": "09:00",
                "end": "11:00",
            }
            AvailabilitySnapshot.objects.update_or_create(
                workspace_id=self.provider.workspace_id,
                defaults={"windows": [window], "version": index + 1},
            )
            row.refresh_from_db()
            offer = contract_for(row)
            offer["serviceRequest"]["status"] = "waiting_schedule"
            offer["serviceRequest"]["clientDecision"] = "approved"
            offer["serviceRequest"]["proposedWindows"] = [window]
            offer["proposedWindows"] = [window]
            row = upsert_from_contract(
                offer,
                provider=self.provider,
                workspace_id=self.provider.workspace_id,
            )
            row.refresh_from_db()
            self.assertEqual(row.status, "waiting_schedule", key)
            self.assertEqual(row.proposed_windows, [window], key)

            self.force_portal(key)
            scheduled = self.client.post(
                reverse("corporate:portal_schedule", args=[row.id]),
                {"source_id": window["sourceId"]},
            )
            self.assertEqual(scheduled.status_code, 302, key)
            row.refresh_from_db()
            self.assertEqual(row.status, "schedule_requested", key)
            self.assertEqual(row.client_decision, "schedule_selected", key)
            self.assertEqual(row.schedule_request["sourceId"], window["sourceId"])

            foreign_key = keys[(index + 1) % len(keys)]
            self.force_portal(foreign_key)
            denied = self.client.post(reverse("corporate:portal_approve", args=[row.id]))
            self.assertEqual(denied.status_code, 403, f"{foreign_key} must not mutate {key}")
