from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
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


class PortalV1832PolishTests(TestCase):
    def setUp(self):
        self.provider = ServiceProvider.objects.create(
            id="provider_v1832_polish",
            slug="provider-v1832-polish",
            name="Provider 18.32",
            display_name="Provider 18.32",
            workspace_id="ws-v1832-polish",
            active=True,
        )
        self.organization = Organization.objects.create(
            id="org_v1832_polish",
            slug="org-v1832-polish",
            name="Org 18.32",
            display_name="Org 18.32",
            active=True,
        )
        OrganizationProvider.objects.create(
            organization=self.organization,
            provider=self.provider,
            active=True,
            is_default=True,
        )
        self.channel = PortalChannel.objects.create(
            id="portal_v1832_polish",
            organization=self.organization,
            slug="polish",
            display_name="Portal Polish",
            default_provider=self.provider,
            active=True,
        )
        self.user = get_user_model().objects.create_user(username="portal_v1832_polish")
        PortalChannelMembership.objects.create(
            user=self.user,
            portal_channel=self.channel,
            role="manager",
            active=True,
        )
        self.existing = ServiceRequest.objects.create(
            id="SR_V1832_EXISTING",
            external_request_id="RACE-001",
            organization=self.organization,
            portal_channel=self.channel,
            provider=self.provider,
            workspace_id=self.provider.workspace_id,
            location={"label": "QA"},
            requester={"name": "QA"},
            description="Registro concorrente já confirmado",
            status="new",
        )
        self.client.force_login(self.user)

    def payload(self, external):
        return {
            "organization_slug": self.organization.slug,
            "portal_channel_id": self.channel.id,
            "provider_id": self.provider.id,
            "external_request_id": external,
            "location": "Local QA",
            "description": "Teste de corrida de duplicidade",
        }

    @patch(
        "corporate.portal_dispatch_v1830.portal_v1830.portal_create",
        side_effect=IntegrityError("simulated concurrent unique collision"),
    )
    def test_concurrent_duplicate_integrity_error_becomes_friendly_redirect(self, mocked_create):
        response = self.client.post(reverse("corporate:portal_create"), self.payload("  RACE-001  "))
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/{self.organization.slug}/{self.channel.slug}/", response.url)
        follow = self.client.get(response.url)
        self.assertContains(follow, "Já existe um chamado com esse número.")
        mocked_create.assert_called_once()

    @patch(
        "corporate.portal_dispatch_v1830.portal_v1830.portal_create",
        side_effect=IntegrityError("simulated unrelated integrity failure"),
    )
    def test_unrelated_integrity_error_is_not_hidden(self, mocked_create):
        with self.assertRaises(IntegrityError):
            self.client.post(reverse("corporate:portal_create"), self.payload("RACE-NOT-EXISTING"))
        mocked_create.assert_called_once()
