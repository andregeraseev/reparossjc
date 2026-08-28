import hashlib
import re
import secrets
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .models import SupportAccessLog, SupportAccount, SupportDevice, SupportEvent, SupportSnapshot

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,120}$")
_SAFE_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_ALLOWED_DETAIL_KEYS = {
    "id", "recordId", "requestId", "quoteId", "jobId", "taskId", "batchId", "sourceId",
    "count", "totalCount", "pendingCount", "syncedCount", "conflicts", "sent", "pulled",
    "status", "state", "operation", "source", "target", "tab", "step", "code",
    "httpStatus", "route", "durationMs", "elapsedMs", "version", "serverVersion", "schemaVersion",
    "available", "configured", "online", "notificationsAllowed", "hasBackup", "ageMinutes",
    "date", "start", "end", "errorType", "line", "column", "stackSignature",
}


class DeviceAlreadyRegistered(ValueError):
    pass


def token_hash(token):
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def account_key_hash(account_key):
    clean = safe_identifier(account_key, prefix="accountKey")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def safe_account_hash(value):
    raw = str(value or "").strip().lower()
    if not _SAFE_HASH_RE.fullmatch(raw):
        raise ValueError("invalid supportAccountHash")
    return raw


def generate_support_code():
    for _ in range(30):
        body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        code = f"RSJC-{body[:4]}-{body[4:]}"
        if not SupportAccount.objects.filter(support_code=code).exists():
            return code
    raise RuntimeError("unable to generate unique support code")


def clean_text(value, limit=240):
    text = str(value or "")
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", text)
    text = re.sub(r"(?i)(token|password|senha|api[_ -]?key)\s*[:=]\s*[^\s,;]+", r"\1=[redacted]", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email]", text)
    text = re.sub(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}(?!\d)", "[phone]", text)
    return text[:limit]


def safe_identifier(value, *, prefix="id", limit=120):
    raw = str(value or "").strip()[:limit]
    if not raw or not _SAFE_ID_RE.fullmatch(raw):
        raise ValueError(f"invalid {prefix}")
    return raw


def safe_label(value, limit=100):
    raw = _SAFE_LABEL_RE.sub("_", str(value or "").strip())
    return raw[:limit]


def _safe_int(value, default=0, minimum=0, maximum=10_000_000):
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(maximum, max(minimum, parsed))


def _safe_float(value, default=0.0, minimum=0.0, maximum=1_000_000_000.0):
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(maximum, max(minimum, parsed))


def _safe_route(value):
    route = str(value or "").split("?", 1)[0].split("#", 1)[0]
    return clean_text(route, 180)


def sanitize_detail(detail):
    if not isinstance(detail, dict):
        return {}
    out = {}
    for key, value in detail.items():
        if key not in _ALLOWED_DETAIL_KEYS:
            continue
        if isinstance(value, bool) or value is None:
            out[key] = value
        elif isinstance(value, (int, float)):
            out[key] = value
        elif isinstance(value, str):
            if key == "route":
                out[key] = _safe_route(value)
            else:
                out[key] = clean_text(value, 600 if key == "stackSignature" else 260)
    return out


def sanitize_device_info(value):
    if not isinstance(value, dict):
        value = {}
    return {
        "platform": clean_text(value.get("platform") or "android", 32),
        "manufacturer": clean_text(value.get("manufacturer"), 80),
        "model": clean_text(value.get("model"), 120),
        "androidRelease": clean_text(value.get("androidRelease"), 40),
        "androidSdk": _safe_int(value.get("androidSdk")),
        "appVersion": clean_text(value.get("appVersion") or value.get("appVersionName"), 40),
        "appVersionCode": _safe_int(value.get("appVersionCode"), maximum=10_000_000_000),
    }


def sanitize_snapshot(data):
    if not isinstance(data, dict):
        return {}

    def pick(section, allowed):
        src = data.get(section)
        if not isinstance(src, dict):
            return {}
        out = {}
        for key in allowed:
            if key not in src:
                continue
            value = src[key]
            if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
                out[key] = value
            elif isinstance(value, str):
                out[key] = clean_text(value, 500)
        return out

    return {
        "app": pick("app", {"version", "versionCode", "schemaVersion", "dataModelVersion"}),
        "device": pick("device", {"platform", "manufacturer", "model", "androidRelease", "androidSdk", "notificationsAllowed", "freeBytes", "totalBytes", "lowStorage"}),
        "workspace": pick("workspace", {"workspaceId", "role"}),
        "counts": pick("counts", {"clients", "quotes", "jobs", "inventory", "tasks", "corporateRequests"}),
        "sync": pick("sync", {"pendingCount", "syncedCount", "lastSyncAt", "corporateConfigured", "corporateLastSyncAt", "corporateLastErrorCode"}),
        "backup": pick("backup", {"lastBackupAt", "hasBackup"}),
        "liveUpdate": pick("liveUpdate", {"available", "notificationsAllowed", "active", "status"}),
        "storage": pick("storage", {"freeBytes", "totalBytes", "freePercent", "lowStorage"}),
        "support": pick("support", {"localEventCount", "continuousSharing", "generatedAt", "privacyVersion"}),
    }


def parse_client_datetime(value):
    now = timezone.now()
    if not value:
        return now
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return now
    if dt > now + timedelta(minutes=10):
        return now
    if dt < now - timedelta(days=120):
        return now - timedelta(days=120)
    return dt


def bootstrap_device(*, account_key, workspace_id, installation_id, display_name="", device_info=None, current_token=""):
    hashed_account_key = account_key_hash(account_key)
    installation_id = safe_identifier(installation_id, prefix="installationId")
    workspace_id = safe_label(workspace_id, 100)
    display_name = clean_text(display_name, 160)

    with transaction.atomic():
        account, _created = SupportAccount.objects.select_for_update().get_or_create(
            account_key_hash=hashed_account_key,
            defaults={
                "support_code": generate_support_code(),
                "workspace_id": workspace_id,
                "display_name": display_name,
            },
        )
        account.workspace_id = workspace_id
        if display_name:
            account.display_name = display_name
        account.last_seen_at = timezone.now()
        account.save(update_fields=["workspace_id", "display_name", "last_seen_at"])

        info = sanitize_device_info(device_info or {})
        device = SupportDevice.objects.select_for_update().filter(account=account, installation_id=installation_id).first()
        if device is not None:
            current_hash = token_hash(current_token)
            if not current_token or not secrets.compare_digest(device.token_hash, current_hash):
                raise DeviceAlreadyRegistered("support device is already registered")
        token = secrets.token_urlsafe(32)
        defaults = {
            "token_hash": token_hash(token),
            "platform": info["platform"],
            "manufacturer": info["manufacturer"],
            "model": info["model"],
            "android_release": info["androidRelease"],
            "android_sdk": info["androidSdk"],
            "app_version": info["appVersion"],
            "app_version_code": info["appVersionCode"],
            "active": True,
        }
        if device is None:
            device = SupportDevice.objects.create(account=account, installation_id=installation_id, **defaults)
        else:
            for key, value in defaults.items():
                setattr(device, key, value)
            device.save()
    return account, device, token


def prune_device_data(device, *, max_events=3000, max_snapshots=50, max_event_days=90, max_snapshot_days=90):
    now = timezone.now()
    event_ids = list(
        SupportEvent.objects.filter(device=device)
        .order_by("-occurred_at", "-id")
        .values_list("id", flat=True)[max_events:]
    )
    if event_ids:
        SupportEvent.objects.filter(id__in=event_ids).delete()
    SupportEvent.objects.filter(device=device, occurred_at__lt=now - timedelta(days=max_event_days)).delete()

    snapshot_ids = list(
        SupportSnapshot.objects.filter(device=device)
        .order_by("-created_at")
        .values_list("id", flat=True)[max_snapshots:]
    )
    if snapshot_ids:
        SupportSnapshot.objects.filter(id__in=snapshot_ids).delete()
    SupportSnapshot.objects.filter(device=device, created_at__lt=now - timedelta(days=max_snapshot_days)).delete()


def purge_expired_support_data(*, event_days=90, snapshot_days=90, access_days=180):
    now = timezone.now()
    event_deleted, _ = SupportEvent.objects.filter(occurred_at__lt=now - timedelta(days=event_days)).delete()
    snapshot_deleted, _ = SupportSnapshot.objects.filter(created_at__lt=now - timedelta(days=snapshot_days)).delete()
    access_deleted, _ = SupportAccessLog.objects.filter(created_at__lt=now - timedelta(days=access_days)).delete()
    return {
        "events": event_deleted,
        "snapshots": snapshot_deleted,
        "accessLogs": access_deleted,
    }
