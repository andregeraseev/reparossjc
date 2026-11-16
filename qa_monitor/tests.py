import base64
import hashlib
import json
import uuid
from datetime import timedelta
from io import BytesIO, StringIO
from time import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.db import connections
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BugReport, LoginWindow, Session, StaffAccount, StaffSession, Tester
from .site_auth import COOKIE

LOGIN = "/qa/login/"
ENDPOINT = "/api/rsjc-qa/v1/sessions/"
TOKEN = "A" * 43
PASSWORD = "fixture-local-password-only"


class QaSiteTests(TestCase):
    databases = {"default", "rsjc_qa"}

    @classmethod
    def setUpTestData(cls):
        cls.qa_user = StaffAccount.objects.create(username="qa-equipe", password_hash=make_password(PASSWORD))
        cls.tester = Tester.objects.create(code="qa-01", token_hash=hashlib.sha256(TOKEN.encode()).hexdigest())

    def payload(self):
        return dict(protocol=1, id=str(uuid.uuid4()), device=str(uuid.uuid4()), version="18.47",
                    sdk=36, form="phone", started=int(time()), duration=10,
                    events=[dict(step="agenda", result="opened", at=2),
                            dict(step="save_jobs", result="verified", at=7, ms=24)])

    def send(self, payload, token=TOKEN, *, secure=True):
        return self.client.post(ENDPOINT, json.dumps(payload), content_type="application/json",
                                secure=secure, HTTP_AUTHORIZATION=f"Bearer {token}")

    def login(self, client=None):
        client = client or self.client
        response = client.get(LOGIN, secure=True)
        self.assertContains(response, "Painel privado de testes")
        return client.post(LOGIN, {"username": self.qa_user.username, "password": PASSWORD,
                                   "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
                           secure=True, HTTP_REFERER="https://testserver" + LOGIN)

    def test_site_and_qa_tables_are_isolated(self):
        self.assertContains(self.client.get("/", secure=True), "Reparos SJC")
        self.assertNotContains(self.client.get("/", secure=True), "Painel privado de testes")
        qa_tables = set(connections["rsjc_qa"].introspection.table_names())
        site_tables = set(connections["default"].introspection.table_names())
        self.assertIn("qa_monitor_session", qa_tables)
        self.assertIn("qa_monitor_bugreport", qa_tables)
        self.assertIn("qa_monitor_staffaccount", qa_tables)
        self.assertNotIn("auth_user", qa_tables)
        self.assertFalse({name for name in site_tables if name.startswith("qa_monitor_")})
        self.assertEqual(self.tester._state.db, "rsjc_qa")

    def test_site_staff_session_has_no_qa_access(self):
        user = get_user_model().objects.create_user("admin-site", is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get("/qa/", secure=True)
        self.assertRedirects(response, LOGIN, fetch_redirect_response=False)
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_staff_login_requires_csrf_and_sets_its_own_cookie(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(LOGIN, {"username": self.qa_user.username, "password": PASSWORD},
                                     secure=True).status_code, 403)
        response = self.login(client)
        self.assertRedirects(response, "/qa/", fetch_redirect_response=False)
        cookie = response.cookies[COOKIE]
        self.assertEqual(cookie["path"], "/qa/")
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertTrue(cookie["secure"] and cookie["httponly"])
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)
        self.assertNotEqual(StaffSession.objects.get().key_hash, cookie.value)
        self.assertEqual(client.get("/qa/", secure=True).status_code, 200)
        self.assertContains(client.get("/", secure=True), "Reparos SJC")

    def test_logout_revokes_the_cookie_record(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.login(client).status_code, 302)
        self.assertEqual(client.get("/qa/logout/", secure=True).status_code, 405)
        self.assertEqual(client.post("/qa/logout/", secure=True).status_code, 403)
        response = client.post("/qa/logout/", {"csrfmiddlewaretoken": client.cookies["csrftoken"].value},
                               secure=True, HTTP_REFERER="https://testserver/qa/")
        self.assertRedirects(response, LOGIN, fetch_redirect_response=False)
        self.assertFalse(StaffSession.objects.exists())
        self.assertEqual(client.get("/qa/", secure=True).status_code, 302)

    def test_android_protocol_stays_compatible_and_is_idempotent(self):
        payload = self.payload()
        self.assertEqual(self.send(payload, "Z" * 43).status_code, 401)
        response = self.send(payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": payload["id"]})
        self.assertEqual(self.send(payload).status_code, 200)
        self.assertEqual(self.send({**payload, "duration": 11}).status_code, 409)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(Session.objects.get()._state.db, "rsjc_qa")
        self.assertEqual(self.login().status_code, 302)
        detail = self.client.get(reverse("qa_detail", args=[payload["id"]]), secure=True)
        self.assertContains(detail, "24 ms")
        self.assertNotContains(detail, TOKEN)

    def test_api_rejects_operational_payload_and_http(self):
        payload = self.payload()
        self.assertIn(self.send(payload, secure=False).status_code, [301, 403])
        self.assertEqual(self.send({**payload, "telefone": "valor-ficticio"}).status_code, 422)
        self.assertEqual(self.send({**payload, "events": [{"step": "app_error", "result": "cliente", "at": 2}]}).status_code, 422)
        self.assertFalse(Session.objects.exists())

    def test_login_limiting_isolated_from_site(self):
        now = timezone.now().replace(second=0, microsecond=0)
        with patch("qa_monitor.site_auth.timezone.now", return_value=now):
            for _ in range(10):
                self.assertEqual(self.client.post(LOGIN, {}, secure=True).status_code, 200)
            self.assertEqual(self.client.post(LOGIN, {}, secure=True).status_code, 429)
        self.assertEqual(LoginWindow.objects.get()._state.db, "rsjc_qa")
        self.assertContains(self.client.get("/", secure=True), "Reparos SJC")

    def test_pruning_expires_only_qa_records(self):
        current = self.payload()
        other = self.payload()
        for payload in (current, other):
            self.assertEqual(self.send(payload).status_code, 201)
        old = timezone.now() - timedelta(days=31)
        Session.objects.filter(pk=other["id"]).update(received_at=old)
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.client.get(reverse("qa_detail", args=[other["id"]]), secure=True).status_code, 404)
        StaffSession.objects.create(key_hash="f" * 64, staff=self.qa_user, expires_at=old)
        LoginWindow.objects.create(key="old", started=old)
        call_command("rsjc_qa_prune", stdout=StringIO())
        self.assertEqual(str(Session.objects.get().pk), current["id"])
        self.assertFalse(StaffSession.objects.filter(pk="f" * 64).exists())
        self.assertFalse(LoginWindow.objects.filter(pk="old").exists())

    def bug(self, session="", picture="", events=None):
        return dict(id=str(uuid.uuid4()), sdk=36, version="18.50", screen="agenda",
                    description="Agenda não abriu.\n<em>Texto do testador</em>",
                    session=session, events=events or [], screenshot=picture)

    def send_bug(self, payload, token=TOKEN, secure=True):
        return self.client.post("/api/rsjc-qa/v1/bugs/", json.dumps(payload), content_type="application/json",
                                secure=secure, HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_v2_actions_are_bounded_and_v1_stays_compatible(self):
        payload = self.payload()
        payload["events"].append(dict(step="edit_payment", result="acted", at=8))
        self.assertEqual(self.send(payload).status_code, 422)
        payload["protocol"] = 2
        payload["version"] = "18.50"
        self.assertEqual(self.send(payload).status_code, 201)
        wrong = {**payload, "id": str(uuid.uuid4()), "events": [dict(step="search", result="acted", at=1, value="free text")]}
        self.assertEqual(self.send(wrong).status_code, 422)
        oversized = {**wrong, "events": [dict(step="search", result="acted", at=1)] * 501}
        self.assertEqual(self.send(oversized).status_code, 422)

    def test_bug_with_jpeg_and_timeline_stays_private(self):
        from PIL import Image
        jpeg = BytesIO()
        Image.new("RGB", (120, 84), "#03234d").save(jpeg, "JPEG")
        session = self.payload()
        self.assertEqual(self.send(session).status_code, 201)
        bug = self.bug(session["id"], base64.b64encode(jpeg.getvalue()).decode(),
                       [dict(step="open_bug", result="acted", at=9)])
        self.assertEqual(self.send_bug(bug, "Z" * 43).status_code, 401)
        self.assertIn(self.send_bug(bug, secure=False).status_code, (301, 403))
        self.assertEqual(self.send_bug(bug).status_code, 201)
        self.assertEqual(self.send_bug(bug).status_code, 200)
        self.assertEqual(self.send_bug({**bug, "description": "outro"}).status_code, 409)
        self.assertEqual(BugReport.objects.count(), 1)
        receipt = self.send_bug(bug)
        self.assertEqual(receipt.json(), {"id": bug["id"]})
        screenshot = reverse("qa_bug_screenshot", args=[bug["id"]])
        detail = reverse("qa_bug_detail", args=[bug["id"]])
        self.assertEqual(self.client.get(screenshot, secure=True).status_code, 302)
        self.assertEqual(self.client.get(detail, secure=True).status_code, 302)
        self.assertEqual(self.login().status_code, 302)
        self.assertContains(self.client.get("/qa/bugs/", secure=True), "Agenda")
        view = self.client.get(detail, secure=True)
        self.assertContains(view, "Abrir relato")
        self.assertContains(view, "Abrir sessão completa")
        self.assertContains(view, "&lt;em&gt;Texto do testador&lt;/em&gt;")
        image = self.client.get(screenshot, secure=True)
        self.assertEqual(image.content, jpeg.getvalue())
        self.assertIn("no-store", image.headers["Cache-Control"])
        self.assertEqual(image.headers["Content-Type"], "image/jpeg")

    def test_text_only_and_invalid_reports(self):
        bug = self.bug()
        for invalid in (
            {**bug, "description": " "},
            {**bug, "screenshot": base64.b64encode(b"not a jpeg").decode()},
            {**bug, "events": [dict(step="open_bug", result="acted", at=9)]},
            {**bug, "screen": "Texto digitado na ficha"},
        ):
            self.assertEqual(self.send_bug(invalid).status_code, 422)
        self.assertEqual(self.send_bug(bug).status_code, 201)
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.client.get(reverse("qa_bug_screenshot", args=[bug["id"]]), secure=True).status_code, 404)
        old = timezone.now() - timedelta(days=31)
        BugReport.objects.filter(pk=bug["id"]).update(received_at=old)
        self.assertEqual(self.client.get(reverse("qa_bug_detail", args=[bug["id"]]), secure=True).status_code, 404)
        call_command("rsjc_qa_prune", stdout=StringIO())
        self.assertFalse(BugReport.objects.exists())
