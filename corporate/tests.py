import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AvailabilitySnapshot, Organization, PartnerMembership, ServiceRequest
from .services import contract_for


@override_settings(CORPORATE_OPERATOR_TOKEN="test-operator-token", CORPORATE_DEFAULT_WORKSPACE_ID="ws_test")
class CorporateApiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(id="org_amil_demo", slug="amil-demo", name="Amil", display_name="Amil", demo=True)
        User = get_user_model()
        self.user = User.objects.create_user(username="amil", password="test-pass-123")
        PartnerMembership.objects.create(user=self.user, organization=self.org, role="manager")

    def auth(self):
        return {"HTTP_AUTHORIZATION": "Bearer test-operator-token", "HTTP_X_WORKSPACE_ID": "ws_test"}

    def test_health(self):
        r = self.client.get(reverse("corporate:health"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_operator_requires_token(self):
        self.assertEqual(self.client.get(reverse("corporate:operator_requests")).status_code, 401)

    def test_operator_preflight_allows_webview_headers_without_token(self):
        r = self.client.options(
            reverse("corporate:operator_requests"),
            HTTP_ORIGIN="null",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,x-workspace-id,x-user-id",
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertIn("Authorization", r["Access-Control-Allow-Headers"])

    def test_portal_creates_request_and_operator_receives_contract(self):
        self.client.login(username="amil", password="test-pass-123")
        r = self.client.post(
            reverse("corporate:portal_create"),
            {
                "external_request_id": "AMIL-001",
                "location": "Flat 3",
                "requester_name": "Central Amil",
                "description": "Torneira com vazamento",
                "priority": "Normal",
                "category": "Hidráulica",
            },
        )
        self.assertEqual(r.status_code, 302)
        api = self.client.get(reverse("corporate:operator_requests"), **self.auth())
        self.assertEqual(api.status_code, 200)
        payload = api.json()["requests"][0]
        self.assertEqual(payload["format"], "ReparosSJC_Corporate_Request")
        self.assertEqual(payload["serviceRequest"]["externalRequestId"], "AMIL-001")
        self.assertNotIn("privateAgenda", json.dumps(payload))

    def test_operator_upsert_is_idempotent_by_org_and_external_id(self):
        package = {
            "format": "ReparosSJC_Corporate_Request",
            "version": 1,
            "organization": {"id": "org_amil_demo", "slug": "amil-demo", "name": "Amil", "displayName": "Amil"},
            "serviceRequest": {
                "id": "CRLOCAL1",
                "externalRequestId": "AMIL-002",
                "organizationId": "org_amil_demo",
                "organizationName": "Amil",
                "workspaceId": "ws_test",
                "location": {"label": "Flat 2"},
                "requester": {"name": "Amil"},
                "category": "Manutenção",
                "priority": "Normal",
                "description": "Primeiro texto",
                "status": "reviewing",
            },
            "quote": {"id": "Q1", "status": "Enviado", "total": 500},
            "proposedWindows": [],
            "scheduleRequest": None,
            "appointment": None,
        }
        r1 = self.client.post(reverse("corporate:operator_requests"), data=json.dumps(package), content_type="application/json", **self.auth())
        self.assertEqual(r1.status_code, 200)
        package["serviceRequest"]["id"] = "CRLOCAL2"
        package["serviceRequest"]["description"] = "Atualizado"
        package["serviceRequest"]["_serverVersion"] = r1.json()["serviceRequest"]["_serverVersion"]
        r2 = self.client.post(reverse("corporate:operator_requests"), data=json.dumps(package), content_type="application/json", **self.auth())
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(ServiceRequest.objects.filter(organization=self.org, external_request_id="AMIL-002").count(), 1)
        row = ServiceRequest.objects.get(organization=self.org, external_request_id="AMIL-002")
        self.assertEqual(row.description, "Atualizado")
        self.assertEqual(row.quote["total"], 500)

    def test_portal_approval_explicit_offer_and_schedule_flow(self):
        row = ServiceRequest.objects.create(
            id="SR1",
            external_request_id="AMIL-003",
            organization=self.org,
            workspace_id="ws_test",
            description="Teste",
            quote={"id": "Q3", "status": "Enviado", "total": 300},
            status="quote_sent",
        )
        self.client.login(username="amil", password="test-pass-123")
        self.assertEqual(self.client.post(reverse("corporate:portal_approve", args=[row.id])).status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, "quote_approved")
        self.assertEqual(row.proposed_windows, [])

        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        self.assertEqual(
            self.client.post(
                reverse("corporate:operator_availability"),
                data=json.dumps({"windows": [w1]}),
                content_type="application/json",
                **self.auth(),
            ).status_code,
            200,
        )
        row.refresh_from_db()
        package = contract_for(row)
        package["serviceRequest"]["status"] = "waiting_schedule"
        package["serviceRequest"]["clientDecision"] = "approved"
        package["serviceRequest"]["proposedWindows"] = [w1]
        package["proposedWindows"] = [w1]
        offer = self.client.post(reverse("corporate:operator_requests"), data=json.dumps(package), content_type="application/json", **self.auth())
        self.assertEqual(offer.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, "waiting_schedule")
        self.assertEqual(row.proposed_windows, [w1])

        self.assertEqual(self.client.post(reverse("corporate:portal_schedule", args=[row.id]), {"source_id": "W1"}).status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, "schedule_requested")
        self.assertEqual(row.schedule_request["start"], "09:00")

    def test_publication_only_removes_stale_offers_from_waiting_request(self):
        w1 = {"sourceId": "W1", "date": "2099-08-28", "start": "09:00", "end": "11:00"}
        w2 = {"sourceId": "W2", "date": "2099-08-28", "start": "14:00", "end": "16:00"}
        row = ServiceRequest.objects.create(
            id="SRAV",
            external_request_id="AMIL-AV",
            organization=self.org,
            workspace_id="ws_test",
            description="Teste",
            quote={"id": "QAV", "status": "Enviado", "total": 200},
            status="waiting_schedule",
            client_decision="approved",
            proposed_windows=[w1],
        )
        api = self.client.post(
            reverse("corporate:operator_availability"),
            data=json.dumps({"windows": [w2]}),
            content_type="application/json",
            **self.auth(),
        )
        self.assertEqual(api.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.proposed_windows, [])
        self.assertEqual(row.status, "waiting_schedule")
        snap = AvailabilitySnapshot.objects.get(pk="ws_test")
        self.assertEqual(snap.windows, [w2])

    def test_contract_exposes_only_public_schedule_projection(self):
        row = ServiceRequest.objects.create(
            id="SR2",
            external_request_id="AMIL-004",
            organization=self.org,
            workspace_id="ws_test",
            description="Teste",
            proposed_windows=[{"sourceId": "W2", "date": "2099-08-29", "start": "13:00", "end": "15:00"}],
        )
        raw = json.dumps(contract_for(row))
        self.assertIn("proposedWindows", raw)
        self.assertNotIn("clientId", raw)
        self.assertNotIn("blockedReason", raw)
