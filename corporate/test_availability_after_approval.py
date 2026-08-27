import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Organization, PartnerMembership, ServiceRequest


@override_settings(
    CORPORATE_OPERATOR_TOKEN="test-operator-token",
    CORPORATE_DEFAULT_WORKSPACE_ID="ws_test",
)
class AvailabilityAfterApprovalTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            id="org_amil_demo",
            slug="amil-demo",
            name="Amil",
            display_name="Amil",
            demo=True,
        )
        user = get_user_model().objects.create_user(
            username="amil",
            password="test-pass-123",
        )
        PartnerMembership.objects.create(
            user=user,
            organization=self.org,
            role="manager",
        )

    def auth(self):
        return {
            "HTTP_AUTHORIZATION": "Bearer test-operator-token",
            "HTTP_X_WORKSPACE_ID": "ws_test",
        }

    def test_publishing_windows_advances_approved_request_to_waiting_schedule(self):
        row = ServiceRequest.objects.create(
            id="SRAPPROVED",
            external_request_id="AMIL-APPROVED",
            organization=self.org,
            workspace_id="ws_test",
            description="Teste",
            quote={"id": "QAPPROVED", "status": "Enviado", "total": 123},
            status="quote_approved",
            client_decision="approved",
            proposed_windows=[],
        )
        windows = [
            {
                "sourceId": "W1",
                "date": "2026-08-28",
                "start": "09:00",
                "end": "11:00",
            },
            {
                "sourceId": "W2",
                "date": "2026-08-28",
                "start": "14:00",
                "end": "16:00",
            },
        ]

        response = self.client.post(
            reverse("corporate:operator_availability"),
            data=json.dumps({"windows": windows}),
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, "waiting_schedule")
        self.assertEqual(row.client_decision, "approved")
        self.assertEqual(row.proposed_windows, windows)
        self.assertGreaterEqual(row.server_version, 2)

    def test_empty_publication_does_not_advance_newly_approved_request(self):
        row = ServiceRequest.objects.create(
            id="SREMPTY",
            external_request_id="AMIL-EMPTY",
            organization=self.org,
            workspace_id="ws_test",
            description="Teste",
            quote={"id": "QEMPTY", "status": "Enviado", "total": 123},
            status="quote_approved",
            client_decision="approved",
            proposed_windows=[],
        )

        response = self.client.post(
            reverse("corporate:operator_availability"),
            data=json.dumps({"windows": []}),
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, "quote_approved")
        self.assertEqual(row.proposed_windows, [])
