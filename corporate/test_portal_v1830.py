from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    Organization,
    OrganizationProvider,
    PartnerMembership,
    PortalChannel,
    PortalChannelMembership,
    PortalPerson,
    ServiceProvider,
    ServiceRequest,
)


class PortalV1830IsolationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            id="org_amil_demo", slug="amil", name="Amil", display_name="Amil", demo=False, active=True
        )
        self.provider = ServiceProvider.objects.create(
            id="provider_v1830_test",
            slug="reparos-sjc-v1830-test",
            name="Reparos SJC v18.30 Test",
            display_name="Reparos SJC v18.30 Test",
            workspace_id="ws-v1830-test",
            active=True,
        )
        OrganizationProvider.objects.create(
            organization=self.org, provider=self.provider, active=True, is_default=True
        )
        self.juridico = PortalChannel.objects.create(
            id="portal_amil_juridico",
            organization=self.org,
            slug="juridico",
            display_name="Amil Jurídico",
            default_category="Jurídico",
            default_provider=self.provider,
            active=True,
            sort_order=10,
        )
        self.manutencao = PortalChannel.objects.create(
            id="portal_amil_manutencao",
            organization=self.org,
            slug="manutencao",
            display_name="Amil Manutenção",
            default_category="Manutenção",
            default_provider=self.provider,
            active=True,
            sort_order=20,
        )
        User = get_user_model()
        self.user = User.objects.create_user("portal_amil_juridico", password="test-pass")
        PartnerMembership.objects.create(user=self.user, organization=self.org, role="manager", active=True)
        PortalChannelMembership.objects.create(
            user=self.user, portal_channel=self.juridico, role="manager", active=True
        )
        self.person = PortalPerson.objects.create(
            portal_channel=self.juridico,
            name="Pessoa Jurídico",
            role_label="Manutenção local",
            phone="11999990000",
            email="pessoa@example.test",
        )
        self.foreign_person = PortalPerson.objects.create(
            portal_channel=self.manutencao,
            name="Pessoa Manutenção",
            role_label="Manutenção",
        )
        self.legal_request = ServiceRequest.objects.create(
            id="SRLEGAL",
            external_request_id="JUR-1",
            organization=self.org,
            portal_channel=self.juridico,
            provider=self.provider,
            workspace_id=self.provider.workspace_id,
            location={"label": "Jurídico"},
            requester={"name": "Pessoa Jurídico"},
            category="Jurídico",
            description="Chamado visível do Jurídico",
        )
        self.maintenance_request = ServiceRequest.objects.create(
            id="SRMAINT",
            external_request_id="MAN-1",
            organization=self.org,
            portal_channel=self.manutencao,
            provider=self.provider,
            workspace_id=self.provider.workspace_id,
            location={"label": "Manutenção"},
            requester={"name": "Pessoa Manutenção"},
            category="Manutenção",
            description="Chamado que não pode vazar para o Jurídico",
        )
        self.client.force_login(self.user)

    def test_user_only_sees_scoped_portal(self):
        response = self.client.get(reverse("corporate:portal_channel", args=["amil", "juridico"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chamado visível do Jurídico")
        self.assertNotContains(response, "Chamado que não pode vazar para o Jurídico")
        self.assertContains(response, "Pessoa Jurídico")
        self.assertNotContains(response, "Pessoa Manutenção")

    def test_user_cannot_open_other_channel(self):
        response = self.client.get(reverse("corporate:portal_channel", args=["amil", "manutencao"]))
        self.assertEqual(response.status_code, 404)

    def test_portal_api_is_scoped(self):
        response = self.client.get(reverse("corporate:portal_requests_api"))
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()["requests"]}
        self.assertIn("SRLEGAL", ids)
        self.assertNotIn("SRMAINT", ids)

    def test_create_request_with_registered_person_snapshot(self):
        response = self.client.post(
            reverse("corporate:portal_create"),
            {
                "organization_slug": "amil",
                "portal_channel_id": self.juridico.id,
                "provider_id": self.provider.id,
                "portal_person_id": self.person.id,
                "location": "Unidade Jurídico",
                "address": "Endereço de teste",
                "priority": "Normal",
                "category": "Jurídico",
                "description": "Nova solicitação jurídica",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = ServiceRequest.objects.exclude(pk__in=["SRLEGAL", "SRMAINT"]).get()
        self.assertEqual(row.portal_channel, self.juridico)
        self.assertEqual(row.requester["personId"], self.person.id)
        self.assertEqual(row.requester["name"], "Pessoa Jurídico")
        self.assertEqual(row.requester["phone"], "11999990000")

    def test_create_cannot_forge_another_channel(self):
        response = self.client.post(
            reverse("corporate:portal_create"),
            {
                "organization_slug": "amil",
                "portal_channel_id": self.manutencao.id,
                "provider_id": self.provider.id,
                "location": "Unidade",
                "description": "Tentativa indevida",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ServiceRequest.objects.filter(description="Tentativa indevida").exists())

    def test_manager_can_create_person_only_in_own_channel(self):
        response = self.client.post(
            reverse("corporate:portal_person_save"),
            {
                "organization_slug": "amil",
                "portal_channel_id": self.juridico.id,
                "name": "Nova Pessoa",
                "role_label": "Responsável",
                "phone": "123",
                "active": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PortalPerson.objects.filter(portal_channel=self.juridico, name="Nova Pessoa").exists())

        denied = self.client.post(
            reverse("corporate:portal_person_save"),
            {
                "organization_slug": "amil",
                "portal_channel_id": self.manutencao.id,
                "name": "Pessoa Indevida",
                "active": "1",
            },
        )
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(PortalPerson.objects.filter(name="Pessoa Indevida").exists())

    def test_attachment_and_request_mutations_use_channel_scope(self):
        response = self.client.post(reverse("corporate:portal_approve", args=[self.maintenance_request.id]))
        self.assertEqual(response.status_code, 403)
