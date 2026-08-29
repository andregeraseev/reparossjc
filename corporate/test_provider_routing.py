import hashlib
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Organization, OrganizationProvider, PartnerMembership, ServiceProvider, ServiceRequest
from .services import contract_for


@override_settings(CORPORATE_OPERATOR_TOKEN="legacy-token", CORPORATE_DEFAULT_WORKSPACE_ID="ws_reparos")
class ProviderRoutingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            id="org_store",
            slug="loja-central",
            name="Loja Central",
            display_name="Loja Central",
        )
        user = get_user_model().objects.create_user(username="loja", password="test-pass-123")
        PartnerMembership.objects.create(user=user, organization=self.organization, role="manager")

        self.provider_a = self.provider("provider_a", "prestador-a", "Prestador A", "ws_a", "token-provider-a-123456789")
        self.provider_b = self.provider("provider_b", "prestador-b", "Prestador B", "ws_b", "token-provider-b-123456789")
        self.provider_hidden = self.provider("provider_hidden", "prestador-oculto", "Prestador Oculto", "ws_hidden", "token-hidden-provider-123456")
        OrganizationProvider.objects.create(
            organization=self.organization,
            provider=self.provider_a,
            active=True,
            is_default=True,
            sort_order=0,
        )
        OrganizationProvider.objects.create(
            organization=self.organization,
            provider=self.provider_b,
            active=True,
            sort_order=1,
        )
        self.client.login(username="loja", password="test-pass-123")

    @staticmethod
    def provider(provider_id, slug, name, workspace_id, token):
        return ServiceProvider.objects.create(
            id=provider_id,
            slug=slug,
            name=name,
            display_name=name,
            workspace_id=workspace_id,
            operator_token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def auth(workspace_id, token):
        return {"HTTP_X_WORKSPACE_ID": workspace_id, "HTTP_AUTHORIZATION": f"Bearer {token}"}

    def create_request(self, provider_id):
        return self.client.post(
            reverse("corporate:portal_create"),
            {
                "external_request_id": f"LOJA-{provider_id}",
                "provider_id": provider_id,
                "location": "Unidade 1",
                "description": "Reparo hidráulico",
            },
        )

    def test_portal_lists_only_authorized_providers(self):
        response = self.client.get(reverse("corporate:portal"))
        self.assertContains(response, "Prestador A")
        self.assertContains(response, "Prestador B")
        self.assertNotContains(response, "Prestador Oculto")

    def test_portal_routes_request_to_selected_authorized_provider(self):
        response = self.create_request(self.provider_b.id)
        self.assertEqual(response.status_code, 302)
        row = ServiceRequest.objects.get(external_request_id="LOJA-provider_b")
        self.assertEqual(row.provider, self.provider_b)
        self.assertEqual(row.workspace_id, "ws_b")

    def test_portal_rejects_forged_unauthorized_provider(self):
        response = self.create_request(self.provider_hidden.id)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceRequest.objects.filter(external_request_id="LOJA-provider_hidden").exists())

    def test_provider_token_and_workspace_are_scoped(self):
        self.create_request(self.provider_b.id)
        row = ServiceRequest.objects.get(external_request_id="LOJA-provider_b")

        own = self.client.get(
            reverse("corporate:operator_requests") + "?workspace_id=ws_a",
            **self.auth("ws_b", "token-provider-b-123456789"),
        )
        self.assertEqual(own.status_code, 200)
        self.assertEqual([item["serviceRequest"]["id"] for item in own.json()["requests"]], [row.id])

        other = self.client.get(
            reverse("corporate:operator_requests"),
            **self.auth("ws_a", "token-provider-a-123456789"),
        )
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.json()["requests"], [])

        wrong_token = self.client.get(
            reverse("corporate:operator_requests"),
            **self.auth("ws_b", "token-provider-a-123456789"),
        )
        self.assertEqual(wrong_token.status_code, 401)

    def test_provider_cannot_update_request_assigned_to_another_provider(self):
        self.create_request(self.provider_b.id)
        row = ServiceRequest.objects.select_related("organization", "provider").get(external_request_id="LOJA-provider_b")
        payload = contract_for(row)
        payload["serviceRequest"]["workspaceId"] = "ws_a"
        response = self.client.post(
            reverse("corporate:operator_requests"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth("ws_a", "token-provider-a-123456789"),
        )
        self.assertEqual(response.status_code, 403)
        row.refresh_from_db()
        self.assertEqual(row.provider, self.provider_b)
        self.assertEqual(row.workspace_id, "ws_b")

    def test_contract_exposes_provider_identity_but_never_token_hash(self):
        self.create_request(self.provider_a.id)
        row = ServiceRequest.objects.select_related("organization", "provider").get(external_request_id="LOJA-provider_a")
        raw = json.dumps(contract_for(row))
        self.assertIn('"providerName": "Prestador A"', raw)
        self.assertIn('"workspaceId": "ws_a"', raw)
        self.assertNotIn("operator_token_hash", raw)
        self.assertNotIn(self.provider_a.operator_token_hash, raw)
