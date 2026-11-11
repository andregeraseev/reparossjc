import hashlib
import json
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import Client, TestCase

from .models import BackupAccount, BackupVersion
from .views import COLLECTIONS


URL = "/api/rsjc-backup/v1/versions/"


class BackupApiTests(TestCase):
    def setUp(self):
        self.keys = patch.dict("os.environ", {"RSJC_BACKUP_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.keys.start()
        self.addCleanup(self.keys.stop)
        self.alice = self.account("first", "A")
        self.bob = self.account("second", "B")

    def account(self, name, char):
        token = char * 43
        BackupAccount.objects.create(name=name, token_sha256=hashlib.sha256(token.encode()).hexdigest())
        return Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def payload(self, amount=105.50):
        data = {name: [] for name in COLLECTIONS}
        data.update(format="ReparosSJC_Config", schemaVersion=44, settings={},
                    extras={"rsjc_v17_assistant_notes": "[]", "rsjc_v17_7_tasks": "[]"})
        data["jobs"] = [{"id": "ficticio"}]
        data["payments"] = [{"id": "recebimento", "amount": amount, "reimbursementAmount": 5.50}]
        return data

    def post(self, data, client=None, digest=None):
        raw = json.dumps(data).encode("utf-8")
        return (client or self.alice).post(URL, data=raw, content_type="application/json",
            secure=True, HTTP_X_BACKUP_SHA256=digest or hashlib.sha256(raw).hexdigest()), raw

    def test_tls_and_bearer_required(self):
        self.assertEqual(self.alice.get(URL).status_code, 403)
        self.assertEqual(Client().get(URL, secure=True).status_code, 401)
        self.assertEqual(self.alice.get(URL, secure=True).status_code, 200)

    def test_versions_are_immutable_and_repeat_is_idempotent(self):
        first, raw = self.post(self.payload())
        second, _ = self.post(self.payload(120))
        repeated, _ = self.post(self.payload())
        self.assertEqual([first.status_code, second.status_code, repeated.status_code], [201, 201, 200])
        self.assertEqual(first.json()["id"], repeated.json()["id"])
        self.assertEqual(BackupVersion.objects.count(), 2)
        first_url = URL + first.json()["id"] + "/"
        retrieved = self.alice.get(first_url, secure=True)
        self.assertEqual(retrieved.content, raw)
        self.assertEqual(retrieved.headers["X-Backup-SHA256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(retrieved.headers["Cache-Control"], "no-store")
        self.assertNotIn(raw, bytes(BackupVersion.objects.first().ciphertext))
        self.assertEqual(self.alice.get(URL, secure=True).json()["versions"][0]["id"], second.json()["id"])

    def test_isolation_between_accounts(self):
        first, _ = self.post(self.payload())
        self.assertEqual(self.bob.get(URL, secure=True).json()["versions"], [])
        self.assertEqual(self.bob.get(URL + first.json()["id"] + "/", secure=True).status_code, 404)
        independent, _ = self.post(self.payload(), client=self.bob)
        self.assertNotEqual(first.json()["id"], independent.json()["id"])

    def test_bad_digest_incomplete_empty_and_credentials_keep_prior_version(self):
        first, raw = self.post(self.payload())
        self.assertEqual(self.post(self.payload(), digest="0" * 64)[0].status_code, 400)
        missing = self.payload()
        del missing["payments"]
        self.assertEqual(self.post(missing)[0].status_code, 422)
        empty = {**self.payload(), **{key: [] for key in COLLECTIONS}}
        self.assertEqual(self.post(empty)[0].json()["error"], "empty_backup")
        leaking = self.payload()
        leaking["settings"]["nested"] = {"openai_api_key": "ficticio"}
        self.assertEqual(self.post(leaking)[0].status_code, 422)
        self.assertEqual(BackupVersion.objects.count(), 1)
        self.assertEqual(self.alice.get(URL + first.json()["id"] + "/", secure=True).content, raw)

    def test_corrupted_or_unconfigured_storage_refuses_download(self):
        first, _ = self.post(self.payload())
        address = URL + first.json()["id"] + "/"
        BackupVersion.objects.update(ciphertext=b"damaged")
        self.assertEqual(self.alice.get(address, secure=True).status_code, 503)
        with patch.dict("os.environ", {"RSJC_BACKUP_ENCRYPTION_KEY": ""}):
            self.assertEqual(self.post(self.payload(125))[0].status_code, 503)

    def test_pagination(self):
        with patch("cloud_backup.views.PAGE_SIZE", 2):
            versions = [self.post(self.payload(i))[0].json()["id"] for i in range(3)]
            first = self.alice.get(URL, secure=True).json()
            self.assertEqual([x["id"] for x in first["versions"]], versions[:0:-1])
            second = self.alice.get(URL, {"before": first["next"]}, secure=True).json()
            self.assertEqual([x["id"] for x in second["versions"]], versions[:1])
            self.assertIsNone(second["next"])
