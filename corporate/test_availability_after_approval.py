import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AvailabilitySnapshot, Organization, PartnerMembership, ServiceRequest
from .services import contract_for


@override_settings(
    CORPORATE_OPERATOR_TOKEN="test-operator-token",
    CORPORATE_DEFAULT_WORKSPACE_ID="ws_test",
)
class CorporateHardeningTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            id="org_amil_demo",
            slug="amil",
            name="Amil",
            display_name="Amil",
            demo=False,
        )
        user = get_user_model().objects.create_user(username="amil", password="test-pass-123")
        PartnerMembership.objects.create(user=user, organization=self.org, role="manager")

    def auth(self):
        return {
            "HTTP_AUTHORIZATION": "Bearer test-operator-token",
            "HTTP_X_WORKSPACE_ID": "ws_test",
        }

    def publish(self, windows):
        return self.client.post(
            reverse("corporate:operator_availability"),
            data=json.dumps({"windows": windows}),
            content_type="application/json",
            **self.auth(),
        )

    def offer(self, row, windows):
        row.refresh_from_db()
        pkg = contract_for(row)
        pkg["serviceRequest"]["status"] = "waiting_schedule"
        pkg["serviceRequest"]["clientDecision"] = "approved"
        pkg["serviceRequest"]["proposedWindows"] = windows
        pkg["proposedWindows"] = windows
        return self.client.post(
            reverse("corporate:operator_requests"),
            data=json.dumps(pkg),
            content_type="application/json",
            **self.auth(),
        )

    def approved(self, request_id):
        return ServiceRequest.objects.create(
            id=request_id,
            external_request_id=request_id,
            organization=self.org,
            workspace_id="ws_test",
            description="Teste",
            quote={"id": f"Q-{request_id}", "status": "Enviado", "total": 123},
            status="quote_approved",
            client_decision="approved",
        )

    def test_global_publication_does_not_auto_offer_to_approved_request(self):
        row = self.approved("AMIL-APPROVED")
        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        response = self.publish([w1])
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, "quote_approved")
        self.assertEqual(row.proposed_windows, [])

    def test_explicit_subset_is_required_and_moves_request_to_waiting_schedule(self):
        row = self.approved("AMIL-SUBSET")
        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        w2 = {"sourceId": "W2", "date": "2099-08-28", "start": "14:00", "end": "16:00"}
        self.assertEqual(self.publish([w1, w2]).status_code, 200)
        response = self.offer(row, [w2])
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, "waiting_schedule")
        self.assertEqual(row.proposed_windows, [w2])

    def test_past_windows_are_discarded_from_global_availability(self):
        past = {"sourceId": "OLD", "date": "2020-01-01", "start": "09:00", "end": "11:00"}
        future = {"sourceId": "FUT", "date": "2099-01-01", "start": "09:00", "end": "11:00"}
        response = self.publish([past, future])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["windows"], [future])

    def test_stale_server_version_returns_409(self):
        row = self.approved("AMIL-CONFLICT")
        pkg = contract_for(row)
        pkg["serviceRequest"]["_serverVersion"] = row.server_version + 99
        pkg["serviceRequest"]["status"] = "reviewing"
        response = self.client.post(
            reverse("corporate:operator_requests"),
            data=json.dumps(pkg),
            content_type="application/json",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 409)

    def test_portal_reserves_slot_and_removes_it_from_other_request(self):
        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        self.assertEqual(self.publish([w1]).status_code, 200)
        first = self.approved("AMIL-FIRST")
        second = self.approved("AMIL-SECOND")
        self.assertEqual(self.offer(first, [w1]).status_code, 200)
        self.assertEqual(self.offer(second, [w1]).status_code, 200)

        self.client.login(username="amil", password="test-pass-123")
        response = self.client.post(reverse("corporate:portal_schedule", args=[first.id]), {"source_id": "W1"})
        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        second.refresh_from_db()
        snap = AvailabilitySnapshot.objects.get(pk="ws_test")
        self.assertEqual(first.status, "schedule_requested")
        self.assertEqual(first.schedule_request["sourceId"], "W1")
        self.assertEqual(second.proposed_windows, [])
        self.assertEqual(snap.windows, [])

    def test_reserved_slot_cannot_be_reintroduced_by_next_publication(self):
        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        self.assertEqual(self.publish([w1]).status_code, 200)
        row = self.approved("AMIL-RESERVED")
        self.assertEqual(self.offer(row, [w1]).status_code, 200)
        self.client.login(username="amil", password="test-pass-123")
        self.client.post(reverse("corporate:portal_schedule", args=[row.id]), {"source_id": "W1"})
        self.client.logout()

        response = self.publish([w1])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["windows"], [])

    def test_provider_can_clear_stale_schedule_request_then_republish_slot(self):
        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        self.assertEqual(self.publish([w1]).status_code, 200)
        row = self.approved("AMIL-REOPEN")
        self.assertEqual(self.offer(row, [w1]).status_code, 200)
        self.client.login(username="amil", password="test-pass-123")
        self.client.post(reverse("corporate:portal_schedule", args=[row.id]), {"source_id": "W1"})
        self.client.logout()
        row.refresh_from_db()

        pkg = contract_for(row)
        pkg["serviceRequest"]["status"] = "quote_approved"
        pkg["serviceRequest"]["clientDecision"] = "approved"
        pkg["serviceRequest"]["proposedWindows"] = []
        pkg["serviceRequest"]["scheduleRequest"] = None
        pkg["proposedWindows"] = []
        pkg["scheduleRequest"] = None
        response = self.client.post(
            reverse("corporate:operator_requests"),
            data=json.dumps(pkg),
            content_type="application/json",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertIsNone(row.schedule_request)
        self.assertEqual(row.client_decision, "approved")
        self.assertEqual(row.status, "quote_approved")

        republish = self.publish([w1])
        self.assertEqual(republish.status_code, 200)
        self.assertEqual(republish.json()["windows"], [w1])

    def test_operator_cannot_demote_production_org_back_to_demo(self):
        row = self.approved("AMIL-ORG")
        pkg = contract_for(row)
        pkg["organization"]["slug"] = "amil-demo"
        pkg["organization"]["demo"] = True
        response = self.client.post(
            reverse("corporate:operator_requests"),
            data=json.dumps(pkg),
            content_type="application/json",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.slug, "amil")
        self.assertFalse(self.org.demo)
