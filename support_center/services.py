import hashlib
import re
import secrets
from datetime import datetime

from django.utils import timezone

from .models import SupportAccount, SupportDevice

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_ALLOWED_DETAIL_KEYS = {
    "id", "recordId", "requestId", "quoteId", "jobId", "taskId", "batchId", "sourceId",
    "count", "totalCount", "pendingCount", "syncedCount", "conflicts", "sent", "pulled",
    "status", "state", "operation", "source", "target", "tab", "step", "reason", "code",
    "httpStatus", "route", "durationMs", "elapsedMs", "version", "serverVersion", "schemaVersion",
    "available", "configured", "online", "notificationsAllowed", "hasBackup", "ageMinutes",
    "date", "start", "end", "errorType", "message", "stack", "line", "column",
}


def token_hash(token):
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


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
            out[key] = clean_text(value, 1200 if key == "stack" else 260)
    return out


def sanitize_device_info(value):
    if not isinstance(value, dict):
        value = {}
    return {
        "platform": clean_text(value.get("platform") or "android", 32),
        "manufacturer": clean_text(value.get("manufacturer"), 80),
        "model": clean_text(value.get("model"), 120),
        "androidRelease": clean_text(value.get("androidRelease"), 40),
        "androidSdk": max(0, int(value.get("androidSdk") or 0)),
        "appVersion": clean_text(value.get("appVersion") or value.get("appVersionName"), 40),
        "appVersionCode": max(0, int(value.get("appVersionCode") or 0)),
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
        "device": pick("device", {"platform", "manufacturer", "model", "androidRelease", "androidSdk", "notificationsAllowed"}),
        "workspace": pick("workspace", {"workspaceId", "role"}),
        "counts": pick("counts", {"clients", "quotes", "jobs", "inventory", "tasks", "corporateRequests"}),
        "sync": pick("sync", {"pendingCount", "syncedCount", "lastSyncAt", "lastError", "corporateConfigured", "corporateLastSyncAt", "corporateLastError"}),
        "backup": pick("backup", {"lastBackupAt", "hasBackup"}),
        "liveUpdate": pick("liveUpdate", {"available", "notificationsAllowed", "active", "status"}),
        "storage": pick("storage", {"usage", "quota", "usagePercent"}),
        "support": pick("support", {"localEventCount", "continuousSharing", "generatedAt"}),
    }


def parse_client_datetime(value):
    if not value:
        return timezone.now()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except (TypeError, ValueError):
        return timezone.now()


def bootstrap_device(*, workspace_id, installation_id, display_name="", device_info=None):
    account, created = SupportAccount.objects.get_or_create(
        workspace_id=workspace_id,
        defaults={"support_code": generate_support_code(), "display_name": clean_text(display_name, 160)},
    )
    if display_name and account.display_name != clean_text(display_name, 160):
        account.display_name = clean_text(display_name, 160)
    account.last_seen_at = timezone.now()
    account.save(update_fields=["display_name", "last_seen_at"] if not created else ["last_seen_at"])

    info = sanitize_device_info(device_info or {})
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
    device, device_created = SupportDevice.objects.get_or_create(account=account, installation_id=installation_id, defaults=defaults)
    if not device_created:
        for key, value in defaults.items():
            setattr(device, key, value)
        device.save()
    return account, device, token
