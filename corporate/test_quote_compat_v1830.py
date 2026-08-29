from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Organization, PortalChannel, PortalChannelMembership, ServiceRequest
from .quote_compat import normalize_quote_items


class PortalQuoteCompatibilityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            id="org_quote_test",
            slug="quote-test",
            name="Quote Test",
            display_name="Quote Test",
            active=True,
        )
        self.channel = PortalChannel.objects.create(
            id="portal_quote_test",
            organization=self.org,
            slug="teste",
            display_name="Portal Quote Test",
            default_category="Manutenção",
            active=True,
        )
        self.user = get_user_model().objects.create_user(
            username="portal_quote_test",
            password="test-pass-123",
        )
        PortalChannelMembership.objects.create(
            user=self.user,
            portal_channel=self.channel,
            role="manager",
            active=True,
        )

    def test_normalizer_adds_safe_price_fallback_without_changing_total(self):
        quote = {
            "status": "Enviado",
            "total": 500,
            "items": [{"name": "Serviço", "qty": 1, "total": 500}],
        }
        normalized = normalize_quote_items(quote)
        self.assertEqual(normalized["items"][0]["total"], 500)
        self.assertEqual(normalized["items"][0]["price"], 500)
        self.assertNotIn("price", quote["items"][0])

    def test_v1830_portal_renders_real_total_only_quote_shape(self):
        row = ServiceRequest.objects.create(
            id="SRQUOTECOMPAT",
            external_request_id="QUOTE-001",
            organization=self.org,
            portal_channel=self.channel,
            workspace_id="ws_test",
            description="Teste de orçamento",
            status="quote_sent",
            quote={
                "id": "Q1",
                "status": "Enviado",
                "total": 500,
                "discount": 0,
                "execution": "",
                "payment": "",
                "validity": "",
                "warranty": "",
                "items": [{"name": "Serviço", "qty": 1, "total": 500}],
            },
        )
        row.refresh_from_db()
        self.assertEqual(row.quote["items"][0]["price"], 500)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("corporate:portal_channel", args=[self.org.slug, self.channel.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Serviço")
