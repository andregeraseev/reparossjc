import json

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SupportEvent, SupportSnapshot


@override_settings(SUPPORT_INGEST_ENABLED=True)
class SupportReview4ConsentTests(TestCase):
    def _bootstrap(self):
        response = self.client.post(
            reverse("support_center:api_bootstrap"),
            data=json.dumps({
                "accountKey": "sacct_review4_12345678",
                "workspaceId": "ws_review4",
                "installationId": "sinst_review4_12345678",
                "device": {"platform": "android", "appVersion": "18.27", "appVersionCode": 1827},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _event_payload(self, mode=None, suffix="one"):
        payload = {
            "appVersion": "18.27",
            "events": [{
                "eventId": f"sevt_review4_{suffix}_12345678",
                "action": "corporate_sync",
                "entity": "corporate",
                "severity": "info",
                "detail": {"status": "ok"},
            }],
        }
        if mode is not None:
            payload["mode"] = mode
        return payload

    def _snapshot_payload(self, mode=None):
        payload = {"snapshot": {"app": {"version": "18.27", "versionCode": 1827}, "sync": {"pendingCount": 0}}}
        if mode is not None:
            payload["mode"] = mode
        return payload

    def test_manual_and_legacy_ingest_work_without_continuous_consent(self):
        boot = self._bootstrap()
        token = boot["deviceToken"]
        legacy = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps(self._event_payload(suffix="legacy")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.json()["mode"], "manual")

        manual = self.client.post(
            reverse("support_center:api_snapshot"),
            data=json.dumps(self._snapshot_payload("manual")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        self.assertEqual(manual.status_code, 200)
        self.assertEqual(manual.json()["mode"], "manual")
        self.assertEqual(SupportEvent.objects.count(), 1)
        self.assertEqual(SupportSnapshot.objects.count(), 1)

    def test_continuous_ingest_is_rejected_until_server_consent_is_enabled(self):
        boot = self._bootstrap()
        token = boot["deviceToken"]
        denied_events = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps(self._event_payload("continuous", "denied")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        denied_snapshot = self.client.post(
            reverse("support_center:api_snapshot"),
            data=json.dumps(self._snapshot_payload("continuous")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        self.assertEqual(denied_events.status_code, 403)
        self.assertEqual(denied_snapshot.status_code, 403)
        self.assertEqual(denied_events.json()["code"], "CONTINUOUS_SHARING_DISABLED")
        self.assertEqual(SupportEvent.objects.count(), 0)
        self.assertEqual(SupportSnapshot.objects.count(), 0)

        consent = self.client.post(
            reverse("support_center:api_consent"),
            data=json.dumps({"continuousSharing": True, "privacyVersion": "support-r1"}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        self.assertEqual(consent.status_code, 200)

        allowed_events = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps(self._event_payload("continuous", "allowed")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        allowed_snapshot = self.client.post(
            reverse("support_center:api_snapshot"),
            data=json.dumps(self._snapshot_payload("continuous")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=token,
        )
        self.assertEqual(allowed_events.status_code, 200)
        self.assertEqual(allowed_snapshot.status_code, 200)
        self.assertEqual(allowed_events.json()["mode"], "continuous")
        self.assertEqual(allowed_snapshot.json()["mode"], "continuous")
        self.assertEqual(SupportEvent.objects.count(), 1)
        self.assertEqual(SupportSnapshot.objects.count(), 1)

    def test_invalid_ingest_mode_is_rejected(self):
        boot = self._bootstrap()
        response = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps(self._event_payload("background_forever", "badmode")),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SupportEvent.objects.count(), 0)
