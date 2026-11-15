import hashlib
import json
import uuid
from copy import deepcopy
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from time import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from .models import LoginWindow, Session, Tester


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
        self.assertEqual(page.headers["Referrer-Policy"], "same-origin")
        self.assertEqual(client.post("/qa/login/", secure=True).status_code, 403)
        get_user_model().objects.create_user("qa-review", password="fixture-password", is_staff=True)
        login = client.post("/qa/login/", {
            "username": "qa-review", "password": "fixture-password",
            "csrfmiddlewaretoken": client.cookies["rsjc_r49_csrf"].value,
        }, secure=True, HTTP_REFERER="https://testserver/qa/login/", follow=True)
        self.assertContains(login, "Sessões enviadas")
        cookie = client.cookies["rsjc_r49_session"]
        self.assertTrue(cookie["secure"] and cookie["httponly"])


    def test_optional_write_duration_is_bounded_and_displayed(self):
        self.payload["events"][0]["ms"] = 100
        self.assertEqual(self.post().status_code, 422)
        del self.payload["events"][0]["ms"]
        self.payload["events"][1]["ms"] = 60001
        self.assertEqual(self.post().status_code, 422)
        self.payload["events"][1]["ms"] = 0
        self.assertEqual(self.post().status_code, 201)
        self.client.force_login(get_user_model().objects.create_user("qa-ms", is_staff=True))
        self.assertContains(self.client.get(f"/qa/sessions/{self.payload['id']}/", secure=True), "0 ms")

    def test_login_throttles_post_per_ip(self):
        url = "/qa/login/"
        fixed = timezone.now().replace(minute=0, second=0, microsecond=0)
        with patch("qa_monitor.views.datetime", wraps=timezone.datetime) as clock:
            clock.now.return_value = fixed
            for i in range(10):
                self.assertEqual(self.client.post(url, secure=True, HTTP_X_REAL_IP=f"192.0.2.{i + 1}").status_code, 200)
            blocked = self.client.post(url, secure=True, HTTP_X_REAL_IP="192.0.2.20")
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers["Retry-After"], "300")
            self.assertEqual(self.client.post(url, secure=True, REMOTE_ADDR="192.0.2.10").status_code, 200)
        self.assertIn("max-age=", self.client.get(url, secure=True).headers["Strict-Transport-Security"])

    def test_retention_prunes_only_expired_qa_entries(self):
        self.assertEqual(self.post().status_code, 201)
        first = self.payload["id"]
        self.payload["id"] = str(uuid.uuid4())
        self.assertEqual(self.post().status_code, 201)
        old = timezone.now() - timedelta(days=31)
        Session.objects.filter(pk=first).update(received_at=old)
        LoginWindow.objects.create(key="expired", started=old)
        LoginWindow.objects.create(key="recent", started=timezone.now())
        call_command("rsjc_qa_prune", stdout=StringIO())
        self.assertEqual(str(Session.objects.get().pk), self.payload["id"])
        self.assertEqual(LoginWindow.objects.get().key, "recent")
