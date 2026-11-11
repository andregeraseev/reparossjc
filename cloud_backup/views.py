import hashlib
import hmac
import json
import os
import re

from cryptography.fernet import Fernet, InvalidToken
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import BackupAccount, BackupVersion


MAX_BYTES = 8 * 1024 * 1024
PAGE_SIZE = 25
COLLECTIONS = ("clients", "jobs", "history", "inventory", "inventoryMovements",
               "customServices", "payments", "generalExpenses", "worklog", "tasks")
SECRETS = {"apikey", "aiapikey", "openaiapikey", "aivault", "aidevicecipher",
           "token", "accesstoken", "bearertoken", "cloudtoken", "corporateapitoken",
           "supportdevicetoken", "password", "secret", "clientsecret"}


def response(data, status=200):
    result = JsonResponse(data, status=status)
    result["Cache-Control"] = "no-store"
    return result


def error(code, status):
    return response({"error": code}, status)


def contains_credentials(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if re.sub(r"[^a-z0-9]", "", key.lower()) in SECRETS and item:
                return True
            if contains_credentials(item):
                return True
    elif isinstance(value, list):
        return any(contains_credentials(item) for item in value)
    return False


def invalid_constant(_):
    raise ValueError("Nonfinite number")


def validate(payload):
    data = json.loads(payload.decode("utf-8"), parse_constant=invalid_constant)
    if not isinstance(data, dict) or data.get("format") != "ReparosSJC_Config" or data.get("schemaVersion") != 44:
        raise ValueError("Unsupported backup format")
    if not isinstance(data.get("settings"), dict) or contains_credentials(data):
        raise ValueError("Invalid backup settings")
    extras = data.get("extras", {})
    if not isinstance(extras, dict) or any(
        key not in ("rsjc_paint_height", "rsjc_schedule_defaults", "rsjc_v17_assistant_notes", "rsjc_v17_7_tasks") and not key.startswith("rsjc_paint_rate_")
        for key in extras
    ):
        raise ValueError("Invalid extra settings")
    counts = {}
    for name in COLLECTIONS:
        records = data.get(name)
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("Incomplete backup collection")
        counts[name] = len(records)
    return counts


def account_for(request):
    header = request.headers.get("Authorization", "")
    match = re.fullmatch(r"Bearer ([A-Za-z0-9_-]{43})", header)
    if match is None:
        return None
    digest = hashlib.sha256(match[1].encode("ascii")).hexdigest()
    return BackupAccount.objects.filter(token_sha256=digest, enabled=True).first()


def cipher():
    key = os.environ.get("RSJC_BACKUP_ENCRYPTION_KEY", "")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError):
        return None


def metadata(version):
    return {"id": str(version.pk), "sha256": version.sha256, "size": version.size,
            "createdAt": version.created_at.isoformat(), "counts": version.counts}


def authorize(request):
    if not request.is_secure():
        return None, error("https_required", 403)
    account = account_for(request)
    if account is None:
        return None, error("unauthorized", 401)
    return account, None


@csrf_exempt  # Only a bearer credential is accepted. Django sessions are ignored.
def versions(request):
    account, denied = authorize(request)
    if denied is not None:
        return denied
    collection = BackupVersion.objects.filter(account=account)
    if request.method == "GET":
        before = request.GET.get("before", "")
        if before and not re.fullmatch(r"[1-9][0-9]{0,17}", before):
            return error("invalid_cursor", 400)
        page = collection.filter(pk__lt=int(before)) if before else collection
        rows = list(page.defer("ciphertext").order_by("-id")[:PAGE_SIZE + 1])
        return response({"versions": [metadata(row) for row in rows[:PAGE_SIZE]],
                         "next": str(rows[PAGE_SIZE - 1].pk) if len(rows) > PAGE_SIZE else None})
    if request.method != "POST":
        result = error("method_not_allowed", 405)
        result["Allow"] = "GET, POST"
        return result

    length = request.META.get("CONTENT_LENGTH") or ""
    if not re.fullmatch(r"[0-9]{1,10}", length):
        return error("length_required", 411)
    length = int(length)
    if length <= 0 or length > MAX_BYTES:
        return error("invalid_size", 413)
    if request.content_type != "application/json":
        return error("invalid_content_type", 415)
    expected = request.headers.get("X-Backup-SHA256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        return error("missing_digest", 400)
    payload = request.read(length + 1)
    if len(payload) != length or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), expected):
        return error("digest_mismatch", 400)
    try:
        counts = validate(payload)
    except (ValueError, UnicodeError, RecursionError):
        return error("invalid_backup", 422)
    encryption = cipher()
    if encryption is None:
        return error("storage_unavailable", 503)
    try:
        with transaction.atomic():
            BackupAccount.objects.select_for_update().get(pk=account.pk)
            duplicate = collection.filter(sha256=expected).defer("ciphertext").first()
            if duplicate:
                return response(metadata(duplicate))
            if not any(counts.values()) and collection.exists():
                return error("empty_backup", 422)
            version = collection.create(account=account, sha256=expected, size=length, counts=counts,
                                        ciphertext=encryption.encrypt(payload))
    except IntegrityError:
        duplicate = collection.filter(sha256=expected).defer("ciphertext").first()
        if duplicate:
            return response(metadata(duplicate))
        return error("storage_unavailable", 503)
    return response(metadata(version), 201)


def download(request, version_id):
    account, denied = authorize(request)
    if denied is not None:
        return denied
    if request.method != "GET":
        return error("method_not_allowed", 405)
    version = BackupVersion.objects.filter(account=account, pk=version_id).first()
    if version is None:
        return error("not_found", 404)
    encryption = cipher()
    if encryption is None:
        return error("storage_unavailable", 503)
    try:
        payload = encryption.decrypt(bytes(version.ciphertext))
    except InvalidToken:
        return error("storage_integrity", 503)
    if len(payload) != version.size or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), version.sha256):
        return error("storage_integrity", 503)
    result = HttpResponse(payload, content_type="application/json")
    result["X-Backup-SHA256"] = version.sha256
    result["Content-Length"] = str(version.size)
    result["Cache-Control"] = "no-store"
    result["Content-Disposition"] = f'attachment; filename="ReparosSJC_backup_{version.pk}.json"'
    return result
