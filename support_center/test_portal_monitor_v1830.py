from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SupportAccount, SupportDevice, SupportSnapshot
from .portal_monitor_v1830 import sanitize_snapshot_v1830


class PortalMonitorV1830Tests(TestCase):
    def test_snapshot_accepts_only_aggregate_portal_counters(self):
        clean = sanitize_snapshot_v1830(
            {
                "app": {"version": "18.30", "versionCode": 1830},
                "portalOps": {
                    "total": 12,
                    "new": 3,
                    "quotePending": 2,
                    "schedulePending": 1,
                    "amilManutencao": 6,
                    "amilJuridico": 2,
                    "clientName": "NÃO PODE ENTRAR",
                    "address": "NÃO PODE ENTRAR",
                    "description": "NÃO PODE ENTRAR",
                    "phone": "11999999999",
                    "portalLabel": "texto livre proibido",
                },
            }
        )
        self.assertEqual(clean["portalOps"]["total"], 12)
        self.assertEqual(clean["portalOps"]["amilManutencao"], 6)
        for forbidden in ("clientName", "address", "description", "phone", "portalLabel"):
            self.assertNotIn(forbidden, clean["portalOps"])
        self.assertNotIn("NÃO PODE ENTRAR", str(clean))

    def test_staff_feed_contains_only_technical_projection(self):
        User = get_user_model()
        staff = User.objects.create_user("support-staff", password="x", is_staff=True)
        account = SupportAccount.objects.create(
            account_key_hash="a" * 64,
            workspace_id="ws_test",
            support_code="RSJC-TEST-0001",
            display_name="Nome privado não deve sair no feed",
            active=True,
        )
        device = SupportDevice.objects.create(
            account=account,
            installation_id="install-test-123",
            token_hash="b" * 64,
            platform="android",
            manufacturer="Samsung",
            model="Test",
            app_version="18.30",
            app_version_code=1830,
            active=True,
        )
        SupportSnapshot.objects.create(
            account=account,
            device=device,
            data={
                "portalOps": {"total": 4, "new": 1, "amilDistrato": 2},
                "sync": {"pendingCount": 1, "corporateConfigured": True, "corporateLastErrorCode": ""},
                "private": {"name": "Cliente", "address": "Rua privada"},
            },
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("support_center:portal_ops_feed"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["privacy"], "aggregate-technical-only")
        self.assertEqual(payload["devices"][0]["portalOps"]["amilDistrato"], 2)
        body = response.content.decode()
        self.assertNotIn("Nome privado", body)
        self.assertNotIn("Rua privada", body)
        self.assertNotIn("Cliente", body)

    def test_feed_requires_staff(self):
        response = self.client.get(reverse("support_center:portal_ops_feed"))
        self.assertEqual(response.status_code, 302)
