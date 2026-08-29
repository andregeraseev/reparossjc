from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    Organization,
    OrganizationProvider,
    PortalChannel,
    PortalChannelMembership,
    ServiceProvider,
    ServiceRequest,
)


class PortalV1830EdgeCaseTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            id="org_edge_v1830",
            slug="edge-v1830",
            name="Edge QA",
            display_name="Edge QA",
        )
        self.provider = ServiceProvider.objects.create(
            id="provider_edge_v1830",
            slug="provider-edge-v1830",
            name="Provider Edge QA",
            display_name="Provider Edge QA",
            workspace_id="ws_edge_v1830",
            active=True,
        )
        OrganizationProvider.objects.create(
            organization=self.organization,
            provider=self.provider,
            active=True,
            is_default=True,
        )
        self.allowed = PortalChannel.objects.create(
            id="portal_edge_allowed",
            organization=self.organization,
            slug="allowed",
            display_name="Portal permitido",
            default_category="Manutenção",
            default_provider=self.provider,
            active=True,
        )
        self.other = PortalChannel.objects.create(
            id="portal_edge_other",
            organization=self.organization,
            slug="other",
            display_name="Portal não autorizado",
            default_category="Manutenção",
            default_provider=self.provider,
            active=True,
        )
        User = get_user_model()
        self.user = User.objects.create_user(username="portal-edge-user", password=None)
        PortalChannelMembership.objects.create(
            user=self.user,
            portal_channel=self.allowed,
            role="manager",
            active=True,
        )
        self.client.force_login(self.user)

    def _create(self, external):
        return self.client.post(
            reverse("corporate:portal_create"),
            {
                "organization_slug": self.organization.slug,
                "portal_channel_id": self.allowed.id,
                "provider_id": self.provider.id,
                "external_request_id": external,
                "location": "Local sintético",
                "description": "Chamado sintético de borda",
            },
        )

    def test_long_external_ids_are_normalized_before_duplicate_check(self):
        prefix = "X" * 120
        first = self._create(prefix + "-primeiro")
        self.assertEqual(first.status_code, 302)
        self.assertEqual(ServiceRequest.objects.filter(organization=self.organization).count(), 1)
        self.assertEqual(
            ServiceRequest.objects.get(organization=self.organization).external_request_id,
            prefix,
        )

        second = self._create(prefix + "-segundo")
        self.assertEqual(second.status_code, 302)
        self.assertEqual(ServiceRequest.objects.filter(organization=self.organization).count(), 1)

    def test_explicit_unauthorized_portal_filter_is_rejected(self):
        ServiceRequest.objects.create(
            id="SR_EDGE_ALLOWED",
            external_request_id="EDGE-ALLOWED",
            organization=self.organization,
            portal_channel=self.allowed,
            provider=self.provider,
            workspace_id=self.provider.workspace_id,
            status="new",
        )
        response = self.client.get(
            reverse("corporate:portal_requests_api"),
            {"portal_channel_id": self.other.id},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "portal forbidden"})
