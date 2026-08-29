from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import SupportAccount, SupportDevice, SupportSnapshot
from .portal_monitor_v1830 import PORTAL_OP_KEYS, sanitize_snapshot_v1830
from .services import account_key_hash


class PortalOpsMonitoringV1830Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="portal-ops-staff",
            password="qa-only-staff-pass",
            is_staff=True,
        )
        self.normal = User.objects.create_user(
            username="portal-ops-normal",
            password="qa-only-normal-pass",
        )
        self.account = SupportAccount.objects.create(
            account_key_hash=account_key_hash("sacct_portal_ops_12345678"),
            workspace_id="ws_portal_ops_qa",
            support_code="RSJC-QA30-PORT1",
            display_name="QA Portal Ops",
        )
        self.device = SupportDevice.objects.create(
            account=self.account,
            installation_id="sinst_portal_ops_12345678",
            token_hash="a" * 64,
            platform="android",
            manufacturer="QA",
            model="Portal Ops Device",
            android_release="16",
            android_sdk=36,
            app_version="18.30",
            app_version_code=1830,
            active=True,
        )

    def test_snapshot_sanitizer_accepts_only_numeric_aggregate_portal_keys(self):
        raw = {
            "portalOps": {
                "total": "9",
                "new": -3,
                "reviewing": 2,
                "quotePending": 3,
                "schedulePending": 4,
                "scheduled": 5,
                "inService": 6,
                "completed": 7,
                "crisTeste": 1,
                "amilJuridico": 2,
                "amilManutencao": 3,
                "amilDistrato": 4,
                "other": 2_000_000,
                "clientName": "NÃO PODE ENTRAR",
                "phone": "11999999999",
                "address": "NÃO PODE ENTRAR",
                "description": "NÃO PODE ENTRAR",
                "requestId": "SR-PRIVADO",
                "portalLabel": "rótulo livre privado",
            }
        }
        clean = sanitize_snapshot_v1830(raw)
        self.assertEqual(set(clean["portalOps"]), set(PORTAL_OP_KEYS))
        self.assertEqual(clean["portalOps"]["total"], 9)
        self.assertEqual(clean["portalOps"]["new"], 0)
        self.assertEqual(clean["portalOps"]["other"], 1_000_000)
        for forbidden in ("clientName", "phone", "address", "description", "requestId", "portalLabel"):
            self.assertNotIn(forbidden, clean["portalOps"])

    def test_staff_feed_re_sanitizes_dirty_stored_snapshot_and_exposes_no_corporate_content(self):
        SupportSnapshot.objects.create(
            account=self.account,
            device=self.device,
            data={
                "portalOps": {
                    "total": 12,
                    "new": 2,
                    "reviewing": 1,
                    "quotePending": 3,
                    "schedulePending": 1,
                    "scheduled": 2,
                    "inService": 1,
                    "completed": 2,
                    "crisTeste": 3,
                    "amilJuridico": 2,
                    "amilManutencao": 5,
                    "amilDistrato": 2,
                    "other": 0,
                    "clientName": "Pessoa privada QA",
                    "phone": "11999999999",
                    "address": "Rua privada QA",
                    "description": "Descrição privada QA",
                    "requestId": "SR-PRIVADO-QA",
                    "imageUrl": "/private/qa.jpg",
                },
                "sync": {
                    "pendingCount": 4,
                    "corporateConfigured": True,
                    "corporateLastSyncAt": "2026-08-29T18:00:00-03:00",
                    "corporateLastErrorCode": "HTTP_409",
                    "corporateLastError": "texto livre privado",
                    "clientName": "Pessoa privada QA",
                },
            },
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse("support_center:portal_ops_feed"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response.headers.get("Cache-Control", ""))

        payload = response.json()
        self.assertEqual(payload["schema"], "rsjc-support-portal-ops-v1")
        self.assertEqual(payload["privacy"], "aggregate-technical-only")
        self.assertEqual(len(payload["devices"]), 1)
        device = payload["devices"][0]
        self.assertEqual(set(device["portalOps"]), set(PORTAL_OP_KEYS))
        self.assertEqual(device["portalOps"]["total"], 12)
        self.assertEqual(
            set(device["sync"]),
            {"pendingCount", "corporateConfigured", "corporateLastSyncAt", "corporateLastErrorCode"},
        )

        body = response.content.decode("utf-8")
        for forbidden in (
            "Pessoa privada QA",
            "11999999999",
            "Rua privada QA",
            "Descrição privada QA",
            "SR-PRIVADO-QA",
            "/private/qa.jpg",
            "texto livre privado",
            '"clientName"',
            '"phone"',
            '"address"',
            '"description"',
            '"requestId"',
            '"imageUrl"',
            '"corporateLastError"',
        ):
            self.assertNotIn(forbidden, body)

    def test_non_staff_cannot_read_aggregate_feed(self):
        self.client.force_login(self.normal)
        response = self.client.get(reverse("support_center:portal_ops_feed"))
        self.assertEqual(response.status_code, 302)
