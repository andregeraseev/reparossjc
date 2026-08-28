import json

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SupportEvent
from .offline import import_offline_package
from .services import account_key_hash


@override_settings(SUPPORT_INGEST_ENABLED=True)
class SupportReview3EventPolicyTests(TestCase):
    def _bootstrap(self):
        response = self.client.post(
            reverse("support_center:api_bootstrap"),
            data=json.dumps({
                "accountKey": "sacct_review3_12345678",
                "workspaceId": "ws_review3",
                "installationId": "sinst_review3_12345678",
                "device": {"platform": "android", "appVersion": "18.27", "appVersionCode": 1827},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_online_event_labels_cannot_carry_free_text(self):
        boot = self._bootstrap()
        response = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps({"events": [{
                "eventId": "sevt_review3_online_12345678",
                "action": "corporate_sync_cliente_Joao",
                "entity": "cliente_Maria",
                "severity": "error",
                "detail": {"httpStatus": 409},
            }]}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        event = SupportEvent.objects.get()
        self.assertEqual(event.action, "unknown_event")
        self.assertEqual(event.entity, "system")
        self.assertNotIn("Joao", event.action)
        self.assertNotIn("Maria", event.entity)

    def test_online_known_event_labels_are_preserved(self):
        boot = self._bootstrap()
        response = self.client.post(
            reverse("support_center:api_events"),
            data=json.dumps({"events": [{
                "eventId": "sevt_review3_known_12345678",
                "action": "corporate_sync",
                "entity": "corporate",
                "detail": {"status": "ok"},
            }]}),
            content_type="application/json",
            HTTP_X_SUPPORT_DEVICE_TOKEN=boot["deviceToken"],
        )
        self.assertEqual(response.status_code, 200)
        event = SupportEvent.objects.get()
        self.assertEqual(event.action, "corporate_sync")
        self.assertEqual(event.entity, "corporate")

    def test_offline_event_labels_use_same_strict_policy(self):
        payload = {
            "format": "ReparosSJC_Support_Diagnostic",
            "version": 3,
            "supportAccountHash": account_key_hash("sacct_review3_offline_12345678"),
            "installationId": "sinst_review3_offline_12345678",
            "snapshot": {"app": {"version": "18.27", "versionCode": 1827}},
            "events": [{
                "eventId": "sevt_review3_offline_12345678",
                "action": "backup_save_endereco_privado",
                "entity": "morador_Ana",
                "detail": {"status": "ok"},
            }],
        }
        import_offline_package(payload)
        event = SupportEvent.objects.get()
        self.assertEqual(event.action, "unknown_event")
        self.assertEqual(event.entity, "system")
        self.assertNotIn("endereco", event.action)
        self.assertNotIn("Ana", event.entity)
