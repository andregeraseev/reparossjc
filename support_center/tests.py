import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import SupportAccessLog, SupportAccount, SupportDevice, SupportEvent, SupportSnapshot
from .services import account_key_hash, purge_expired_support_data, sanitize_detail


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

    def test_raw_account_key_is_not_stored(self):
        raw = "sacct_private_12345678"
        self.bootstrap(account_key=raw, installation_id="sinst_hash_12345678")
        account = SupportAccount.objects.get()
        self.assertEqual(account.account_key_hash, account_key_hash(raw))
        self.assertNotIn(raw, account.account_key_hash)

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

    def test_route_sanitizer_removes_query_and_fragment(self):
        detail = sanitize_detail({"route": "/operator/requests?id=secret#fragment", "httpStatus": 409})
        self.assertEqual(detail["route"], "/operator/requests")
        self.assertEqual(detail["httpStatus"], 409)

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

    def test_consent_is_per_device_and_snapshot_cannot_change_it(self):
        boot = self.bootstrap().json()
        response = self.client.post(
            reverse("support_center:api_consent"),
            data=json.dumps({"continuousSharing": True, "privacyVersion": "support-r1-review2"}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        device = SupportDevice.objects.get()
        self.assertTrue(device.continuous_sharing)
        consent_at = device.consent_updated_at

        snapshot = self.client.post(
            reverse("support_center:api_snapshot"),
            data=json.dumps({"snapshot": {"support": {"continuousSharing": False, "privacyVersion": "forged"}}}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(snapshot.status_code, 200)
        device.refresh_from_db()
        self.assertTrue(device.continuous_sharing)
        self.assertEqual(device.privacy_version, "support-r1-review2")
        self.assertEqual(device.consent_updated_at, consent_at)

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
        self.account = SupportAccount.objects.create(account_key_hash=account_key_hash("sacct_central_12345678"), workspace_id="ws_central", support_code="RSJC-ABCD-EFGH", display_name="Oficina")

    def test_staff_can_search_open_and_is_audited_without_cache(self):
        self.client.force_login(self.staff)
        home = self.client.get(reverse("support_center:dashboard"), {"q": "ABCD"})
        self.assertContains(home, "RSJC-ABCD-EFGH")
        self.assertIn("no-cache", home.headers.get("Cache-Control", ""))
        detail = self.client.get(reverse("support_center:account_detail", kwargs={"support_code": self.account.support_code}))
        self.assertContains(detail, "Saúde atual")
        self.assertIn("no-cache", detail.headers.get("Cache-Control", ""))
        self.assertTrue(SupportAccessLog.objects.filter(account=self.account, user=self.staff, action="view_account").exists())

    def test_non_staff_is_redirected(self):
        user = get_user_model().objects.create_user("normal", password="safe-test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("support_center:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_import_v3_sanitized_offline_diagnostic_without_raw_key(self):
        self.client.force_login(self.staff)
        raw_account_key = "sacct_offline_12345678"
        payload = {
            "format": "ReparosSJC_Support_Diagnostic",
            "version": 3,
            "supportCode": "RSJC-WXYZ-2345",
            "supportAccountHash": account_key_hash(raw_account_key),
            "installationId": "sinst_offline_12345678",
            "snapshot": {
                "app": {"version": "18.27", "versionCode": 1827},
                "device": {"manufacturer": "Samsung", "model": "S23", "androidRelease": "16", "androidSdk": 36},
                "workspace": {"workspaceId": "ws_same_commercial"},
                "sync": {"pendingCount": 2, "corporateLastErrorCode": "HTTP_409"},
                "secret": {"token": "never"},
            },
            "events": [{
                "eventId": "sevt_offline_12345678",
                "occurredAt": timezone.now().isoformat(),
                "action": "corporate_sync_error",
                "entity": "sync",
                "severity": "error",
                "detail": {"httpStatus": 409, "message": "nome privado", "stackSignature": "ux_v2.js:200:1"},
            }],
        }
        self.assertNotIn("supportAccountKey", payload)
        upload = SimpleUploadedFile("diagnostico.json", json.dumps(payload).encode("utf-8"), content_type="application/json")
        response = self.client.post(reverse("support_center:offline_import"), {"diagnostic": upload})
        self.assertEqual(response.status_code, 302)
        account = SupportAccount.objects.get(account_key_hash=account_key_hash(raw_account_key))
        self.assertEqual(account.support_code, "RSJC-WXYZ-2345")
        device = account.devices.get()
        self.assertEqual(device.platform, "offline")
        self.assertTrue(device.installation_id.startswith("offline_"))
        self.assertEqual(account.snapshots.count(), 1)
        event = account.events.get()
        self.assertEqual(event.detail["httpStatus"], 409)
        self.assertNotIn("message", event.detail)
        self.assertTrue(SupportAccessLog.objects.filter(account=account, user=self.staff, action="offline_import").exists())

    def test_timeline_filters_and_groups_repeated_events(self):
        self.client.force_login(self.staff)
        device = SupportDevice.objects.create(account=self.account, installation_id="sinst_filter_12345678", token_hash="a" * 64, manufacturer="Samsung", model="S23", android_release="16", android_sdk=36, app_version="18.27", app_version_code=1827)
        now = timezone.now()
        for idx in range(2):
            SupportEvent.objects.create(account=self.account, device=device, event_id=f"sevt_error_{idx}_12345678", occurred_at=now - timedelta(minutes=idx), action="corporate_sync_error", entity="sync", severity="error", detail={"httpStatus": 409})
        SupportEvent.objects.create(account=self.account, device=device, event_id="sevt_info_12345678", occurred_at=now - timedelta(days=10), action="backup_ok", entity="backup", severity="info")
        response = self.client.get(reverse("support_center:account_detail", kwargs={"support_code": self.account.support_code}), {"severity": "error", "action": "corporate", "period": "24h"})
        self.assertContains(response, "corporate_sync_error")
        self.assertContains(response, "×2")
        self.assertNotContains(response, "backup_ok")
        self.assertContains(response, "Copiar resumo técnico")

    def test_health_is_per_device_and_current_device_drives_header(self):
        self.client.force_login(self.staff)
        old = SupportDevice.objects.create(account=self.account, installation_id="sinst_old_12345678", token_hash="b" * 64, model="Antigo", platform="android", android_sdk=36)
        fresh = SupportDevice.objects.create(account=self.account, installation_id="sinst_new_12345678", token_hash="c" * 64, model="Atual", platform="android", android_sdk=36, app_version="18.27")
        SupportDevice.objects.filter(pk=old.pk).update(last_seen_at=timezone.now() - timedelta(days=20))
        SupportDevice.objects.filter(pk=fresh.pk).update(last_seen_at=timezone.now())
        old.refresh_from_db(); fresh.refresh_from_db()
        SupportSnapshot.objects.create(account=self.account, device=fresh, data={"backup": {"lastBackupAt": timezone.now().isoformat()}, "storage": {"freePercent": 60}, "sync": {"pendingCount": 0}})
        response = self.client.get(reverse("support_center:account_detail", kwargs={"support_code": self.account.support_code}))
        self.assertContains(response, "saúde atual baseada em Atual")
        self.assertContains(response, "Antigo")
        self.assertContains(response, "Atual")
        self.assertContains(response, "saúde 100/100")

    def test_retention_purge_removes_expired_telemetry(self):
        device = SupportDevice.objects.create(account=self.account, installation_id="sinst_retention_12345678", token_hash="d" * 64, model="S23")
        event = SupportEvent.objects.create(account=self.account, device=device, event_id="sevt_old_12345678", occurred_at=timezone.now() - timedelta(days=100), action="old", entity="system")
        snap = SupportSnapshot.objects.create(account=self.account, device=device, data={})
        SupportSnapshot.objects.filter(pk=snap.pk).update(created_at=timezone.now() - timedelta(days=100))
        result = purge_expired_support_data()
        self.assertFalse(SupportEvent.objects.filter(pk=event.pk).exists())
        self.assertFalse(SupportSnapshot.objects.filter(pk=snap.pk).exists())
        self.assertGreaterEqual(result["events"], 1)
        self.assertGreaterEqual(result["snapshots"], 1)
