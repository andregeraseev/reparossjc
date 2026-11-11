import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()


class DoNotRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(condition, label):
    if not condition:
        raise RuntimeError(label)
    print("PASS", label, flush=True)


def probe(origin, output):
    from cloud_backup.models import BackupAccount
    from cloud_backup.views import COLLECTIONS

    smoke = secrets.token_urlsafe(32)
    tester = secrets.token_urlsafe(32)
    for name, token in (("qa-smoke", smoke), ("qa-android", tester)):
        BackupAccount.objects.create(name=name, token_sha256=hashlib.sha256(token.encode()).hexdigest())

    endpoint = origin + "/api/rsjc-backup/v1/versions/"
    client = build_opener(DoNotRedirect)

    def request(url, token=None, body=None, digest=None):
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers.update({"Content-Type": "application/json", "X-Backup-SHA256": digest})
        try:
            with client.open(Request(url, data=body, headers=headers), timeout=15) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def encoded(amount, *, valid=True):
        data = {key: [] for key in COLLECTIONS}
        data.update(format="ReparosSJC_Config", schemaVersion=44, appVersion="18.44", settings={})
        data["jobs"] = [{"id": "qa-cloud-job" if valid else "other", "client": "Cliente fictício"}]
        data["payments"] = [{"id": "qa-pay", "jobId": data["jobs"][0]["id"],
                             "amount": amount, "reimbursementAmount": 5.50}]
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return raw, hashlib.sha256(raw).hexdigest()

    check(request(endpoint)[0] == 401, "TLS público válido e token obrigatório")
    check(request(endpoint, "A" * 43)[0] == 401, "token incorreto recusado")
    first, digest = encoded(105.50)
    status, receipt, _ = request(endpoint, smoke, first, digest)
    check(status == 201 and json.loads(receipt)["sha256"] == digest, "envio e recibo SHA-256")
    first_id = json.loads(receipt)["id"]
    status, duplicate, _ = request(endpoint, smoke, first, digest)
    check(status == 200 and json.loads(duplicate)["id"] == first_id, "envio repetido reaproveita a versão")
    second, digest2 = encoded(120.00)
    status, newer, _ = request(endpoint, smoke, second, digest2)
    check(status == 201 and json.loads(newer)["id"] != first_id, "segunda versão preserva a anterior")
    file_url = endpoint + first_id + "/"
    status, downloaded, headers = request(file_url, smoke)
    check(status == 200 and downloaded == first and headers["X-Backup-SHA256"] == digest,
          "versão anterior baixada byte a byte")
    status, isolated, _ = request(endpoint, tester)
    check(status == 200 and not json.loads(isolated)["versions"] and request(file_url, tester)[0] == 404,
          "conta do celular isolada da bateria automática")
    bad, bad_digest = encoded(130.00, valid=False)
    check(request(endpoint, smoke, bad, bad_digest)[0] == 422, "registro fora do cenário de QA recusado")
    check(request(endpoint, smoke, first, "0" * 64)[0] == 400, "checksum divergente recusado")

    # Limit the lifetime of the service and its generated test credential.
    expires = int((datetime.now(timezone.utc) + timedelta(minutes=90)).timestamp())
    os.umask(0o077)
    output.write_text(json.dumps({"url": origin, "token": tester, "expires": expires}, separators=(",", ":")))


if __name__ == "__main__":
    probe(sys.argv[1], Path(sys.argv[2]))
