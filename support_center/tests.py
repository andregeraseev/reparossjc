import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SupportAccount, SupportDevice, SupportEvent, SupportSnapshot


@override_settings(SUPPORT_INGEST_ENABLED=True)
class SupportApiTests(TestCase):
    def bootstrap(self):
        response = self.client.post(
            reverse("support_center:api_bootstrap"),
            data=json.dumps({
                "workspaceId": "ws_test_support",
                "installationId": "install_123",
                "displayName": "Empresa Teste",
                "device": {"platform": "android", "manufacturer": "Samsung", "model": "S23", "androidRelease": "16", "androidSdk": 36, "appVersion": "18.27", "appVersionCode": 1827},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_bootstrap_generates_stable_support_code_and_rotates_device_token(self):
        first = self.bootstrap()
        second = self.bootstrap()
        self.assertRegex(first["supportCode"], r"^RSJC-[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertEqual(first["supportCode"], second["supportCode"])
        self.assertNotEqual(first["deviceToken"], second["deviceToken"])
        self.assertEqual(SupportAccount.objects.count(), 1)
        self.assertEqual(SupportDevice.objects.count(), 1)
        self.assertNotIn(first["deviceToken"], SupportDevice.objects.get().token_hash)

    def test_events_require_device_token_and_are_sanitized(self):
        boot = self.bootstrap()
        denied = self.client.post(reverse("support_center:api_events"), data="{}", content_type="application/json")
        self.assertEqual(denied.status_code, 401)
        response = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps({"appVersion": "18.27", "events": [{
                "eventId": "evt_1", "occurredAt": "2026-08-27T20:00:00-03:00", "action": "corporate_sync_error", "entity": "system", "severity": "error",
                "detail": {"httpStatus": 409, "message": "token=abc123 email a@b.com", "clientName": "NÃO DEVE ENTRAR"},
            }]}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        event = SupportEvent.objects.get()
        self.assertEqual(event.detail["httpStatus"], 409)
        self.assertNotIn("abc123", event.detail["message"])
        self.assertNotIn("a@b.com", event.detail["message"])
        self.assertNotIn("clientName", event.detail)

    def test_snapshot_keeps_only_diagnostic_whitelist(self):
        boot = self.bootstrap()
        response = self.client.post(
            reverse("support_center:api_snapshot"),
            data=json.dumps({"snapshot": {
                "app": {"version": "18.27", "versionCode": 1827},
                "counts": {"clients": 3, "jobs": 2},
                "sync": {"pendingCount": 1, "corporateLastError": "HTTP 409"},
                "secret": {"token": "must-not-survive"},
            }}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        data = SupportSnapshot.objects.get().data
        self.assertEqual(data["counts"]["clients"], 3)
        self.assertNotIn("secret", data)


class SupportCentralTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user("supporter", password="safe-test-password", is_staff=True)
        self.account = SupportAccount.objects.create(workspace_id="ws_central", support_code="RSJC-ABCD-EFGH", display_name="Oficina")

    def test_staff_can_search_and_open_account(self):
        self.client.force_login(self.staff)
        home = self.client.get(reverse("support_center:dashboard"), {"q": "ABCD"})
        self.assertContains(home, "RSJC-ABCD-EFGH")
        detail = self.client.get(reverse("support_center:account_detail", kwargs={"support_code": self.account.support_code}))
        self.assertContains(detail, "Saúde")

    def test_non_staff_is_redirected(self):
        user = get_user_model().objects.create_user("normal", password="safe-test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("support_center:dashboard"))
        self.assertEqual(response.status_code, 302)
