import hashlib
import json
import uuid
from copy import deepcopy
from time import time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Session, Tester


URL = "/api/rsjc-qa/v1/sessions/"


class QaMonitorTests(TestCase):
    def setUp(self):
        for name, char in (("qa-01", "A"), ("qa-02", "B")):
            Tester.objects.create(code=name, token_hash=hashlib.sha256((char * 43).encode()).hexdigest())
        self.payload = dict(protocol=1, id=str(uuid.uuid4()), device=str(uuid.uuid4()), version="18.45",
                            sdk=36, form="phone", started=int(time()), duration=6,
                            events=[dict(step="jobs", result="opened", at=1),
                                    dict(step="save_jobs", result="verified", at=4)])

    def post(self, data=None, token="A", secure=True):
        kwargs = {"HTTP_AUTHORIZATION": "Bearer " + token * 43} if token else {}
        return self.client.post(URL, json.dumps(self.payload if data is None else data),
                                content_type="application/json", secure=secure, **kwargs)

    def test_https_and_distinct_token_required(self):
        self.assertEqual(self.post(secure=False).status_code, 301)
        self.assertEqual(self.post(token=None).status_code, 401)
        self.assertEqual(self.post(token="C").status_code, 401)
        self.assertEqual(self.client.get(URL, secure=True).status_code, 405)
        self.assertFalse(Session.objects.exists())

    def test_idempotency_and_account_isolation(self):
        first = self.post()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json(), {"id": self.payload["id"]})
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post(token="B").status_code, 409)
        changed = deepcopy(self.payload)
        changed["duration"] = 7
        self.assertEqual(self.post(changed).status_code, 409)
        self.assertEqual(Session.objects.get().payload, self.payload)

    def test_private_schema_rejects_business_data_and_malformed_shapes(self):
        changes = [("client", "fictício"), ("version", "texto livre"), ("device", "12345"),
                   ("started", "agora"), ("duration", True), ("sdk", 200), ("events", [{}]),
                   ("events", [{"step": "jobs", "result": "opened", "at": 7}]),
                   ("events", [{"step": "save_jobs", "result": "verified", "at": 1, "value": "dado"}]),
                   ("events", [{"step": "jobs", "result": "verified", "at": 1}]),
                   ("events", [{"step": "app_error", "result": "failed", "at": 1}] * 161),
                   ("events", [{"step": "save_jobs", "result": "failed", "at": 2},
                               {"step": "home", "result": "opened", "at": 1}])]
        for key, value in changes:
            with self.subTest(key=key):
                self.assertEqual(self.post({**self.payload, key: value}).status_code, 422)
        self.assertFalse(Session.objects.exists())

    def test_dashboard_requires_staff_login_and_displays_result(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.client.get("/qa/", secure=True).status_code, 302)
        User = get_user_model()
        regular = User.objects.create_user("qa-test")
        self.client.force_login(regular)
        self.assertEqual(self.client.get("/qa/", secure=True).status_code, 403)
        staff = User.objects.create_user("qa-team", is_staff=True)
        self.client.force_login(staff)
        self.assertContains(self.client.get("/qa/", secure=True), "qa-01")
        detail = self.client.get(f"/qa/sessions/{self.payload['id']}/", secure=True)
        self.assertContains(detail, "Gravação conferida")
        self.assertContains(detail, self.payload["device"][:8])
        self.assertIn("no-store", detail.headers["Cache-Control"])
        self.assertNotContains(detail, "A" * 43)

    def test_dashboard_login_csrf(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get("/qa/login/", secure=True)
        self.assertContains(page, "csrfmiddlewaretoken")
        self.assertEqual(client.post("/qa/login/", secure=True).status_code, 403)
