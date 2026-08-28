import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SupportAccessLog, SupportAccount, SupportDevice, SupportEvent, SupportSnapshot


@override_settings(SUPPORT_INGEST_ENABLED=True)
class SupportApiTests(TestCase):
    def bootstrap(self, *, account_key="sacct_test_12345678", installation_id="sinst_test_12345678", token=""):
        headers = {}
        if token:
            headers["HTTP_X_SUPPORT_DEVICE_TOKEN"] = token
        return self.client.post(
            reverse("support_center:api_bootstrap"),
            data=json.dumps({
                "accountKey": account_key,
                "workspaceId": "ws_test_support",
                "installationId": installation_id,
                "displayName": "Empresa Teste",
                "device": {"platform": "android", "manufacturer": "Samsung", "model": "S23", "androidRelease": "16", "androidSdk": 36, "appVersion": "18.27", "appVersionCode": 1827},
            }),
            content_type="application/json",
            **headers,
        )

    def test_support_account_is_not_keyed_by_workspace(self):
        first = self.bootstrap(account_key="sacct_account_AAAAAAAA", installation_id="sinst_AAAAAAAA")
        second = self.bootstrap(account_key="sacct_account_BBBBBBBB", installation_id="sinst_BBBBBBBB")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first.json()["supportCode"], second.json()["supportCode"])
        self.assertEqual(SupportAccount.objects.filter(workspace_id="ws_test_support").count(), 2)

    def test_existing_device_requires_current_token_to_rotate(self):
        first = self.bootstrap()
        self.assertEqual(first.status_code, 200)
        first_data = first.json()
        denied = self.bootstrap()
        self.assertEqual(denied.status_code, 409)
        rotated = self.bootstrap(token=first_data["deviceToken"])
        self.assertEqual(rotated.status_code, 200)
        self.assertEqual(first_data["supportCode"], rotated.json()["supportCode"])
        self.assertNotEqual(first_data["deviceToken"], rotated.json()["deviceToken"])
        self.assertEqual(SupportAccount.objects.count(), 1)
        self.assertEqual(SupportDevice.objects.count(), 1)

    def test_events_require_device_token_and_drop_free_text(self):
        boot = self.bootstrap().json()
        denied = self.client.post(reverse("support_center:api_events"), data="{}", content_type="application/json")
        self.assertEqual(denied.status_code, 401)
        response = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps({"appVersion": "18.27", "events": [{
                "eventId": "sevt_test_12345678", "occurredAt": "2026-08-27T20:00:00-03:00", "action": "corporate_sync_error", "entity": "system", "severity": "error",
                "detail": {"httpStatus": 409, "message": "cliente Fulano token=abc123", "stack": "Error: endereço privado", "stackSignature": "ux_v2.js:123:4", "clientName": "NÃO DEVE ENTRAR"},
            }]}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        event = SupportEvent.objects.get()
        self.assertEqual(event.detail["httpStatus"], 409)
        self.assertEqual(event.detail["stackSignature"], "ux_v2.js:123:4")
        self.assertNotIn("message", event.detail)
        self.assertNotIn("stack", event.detail)
        self.assertNotIn("clientName", event.detail)

    def test_duplicate_events_are_reported_not_reinserted(self):
        boot = self.bootstrap().json()
        payload = {"events": [{"eventId": "sevt_dup_12345678", "action": "sync_ok", "entity": "sync", "detail": {"status": "ok"}}]}
        first = self.client.post(reverse("support_center:api_events"), data=json.dumps(payload), content_type="application/json", HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"])
        second = self.client.post(reverse("support_center:api_events"), data=json.dumps(payload), content_type="application/json", HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"])
        self.assertEqual(first.json()["accepted"], 1)
        self.assertEqual(second.json()["accepted"], 0)
        self.assertEqual(second.json()["duplicates"], 1)
        self.assertEqual(SupportEvent.objects.count(), 1)

    def test_snapshot_keeps_only_diagnostic_whitelist(self):
        boot = self.bootstrap().json()
        response = self.client.post(
            reverse("support_center:api_snapshot"),
            data=json.dumps({"snapshot": {
                "app": {"version": "18.27", "versionCode": 1827},
                "counts": {"clients": 3, "jobs": 2},
                "sync": {"pendingCount": 1, "corporateLastError": "texto livre não deve sobreviver", "corporateLastErrorCode": "HTTP_409"},
                "support": {"continuousSharing": False, "privacyVersion": "support-r1"},
                "secret": {"token": "must-not-survive"},
            }}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        data = SupportSnapshot.objects.get().data
        self.assertEqual(data["counts"]["clients"], 3)
        self.assertEqual(data["sync"]["corporateLastErrorCode"], "HTTP_409")
        self.assertNotIn("corporateLastError", data["sync"])
        self.assertNotIn("secret", data)

    def test_consent_is_per_device(self):
        boot = self.bootstrap().json()
        response = self.client.post(
            reverse("support_center:api_consent"),
            data=json.dumps({"continuousSharing": True, "privacyVersion": "support-r1"}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        device = SupportDevice.objects.get()
        self.assertTrue(device.continuous_sharing)
        self.assertIsNotNone(device.consent_updated_at)

    def test_payload_limit_rejects_oversized_bootstrap(self):
        response = self.client.post(
            reverse("support_center:api_bootstrap"),
            data=json.dumps({"accountKey": "sacct_big_12345678", "installationId": "sinst_big_12345678", "padding": "x" * 20000}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 413)


class SupportCentralTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user("supporter", password="safe-test-password", is_staff=True)
        self.account = SupportAccount.objects.create(account_key="sacct_central_12345678", workspace_id="ws_central", support_code="RSJC-ABCD-EFGH", display_name="Oficina")

    def test_staff_can_search_open_and_is_audited(self):
        self.client.force_login(self.staff)
        home = self.client.get(reverse("support_center:dashboard"), {"q": "ABCD"})
        self.assertContains(home, "RSJC-ABCD-EFGH")
        detail = self.client.get(reverse("support_center:account_detail", kwargs={"support_code": self.account.support_code}))
        self.assertContains(detail, "Saúde")
        self.assertTrue(SupportAccessLog.objects.filter(account=self.account, user=self.staff, action="view_account").exists())

    def test_non_staff_is_redirected(self):
        user = get_user_model().objects.create_user("normal", password="safe-test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("support_center:dashboard"))
        self.assertEqual(response.status_code, 302)
