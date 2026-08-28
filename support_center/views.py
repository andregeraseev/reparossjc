import hashlib
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .diagnostics import diagnose_account
from .models import SupportAccessLog, SupportAccount, SupportCase, SupportDevice, SupportEvent, SupportSnapshot
from .offline import import_offline_package
from .services import (
    DeviceAlreadyRegistered,
    bootstrap_device,
    clean_text,
    parse_client_datetime,
    prune_device_data,
    safe_identifier,
    safe_label,
    sanitize_detail,
    sanitize_snapshot,
    token_hash,
)


class PayloadTooLarge(ValueError):
    pass


def _json_body(request, max_bytes=262_144):
    try:
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        declared = 0
    if declared > max_bytes:
        raise PayloadTooLarge("payload too large")
    raw = request.body or b"{}"
    if len(raw) > max_bytes:
        raise PayloadTooLarge("payload too large")
    try:
        value = json.loads(raw.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid JSON")


def _cors(response):
    response["Access-Control-Allow-Origin"] = "null"
    response["Access-Control-Allow-Headers"] = "Content-Type, X-Support-Device-Token"
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response["Vary"] = "Origin"
    return response


def _json(payload, status=200):
    return _cors(JsonResponse(payload, status=status))


def _ingest_enabled():
    return bool(getattr(settings, "SUPPORT_INGEST_ENABLED", False))


def _rate_limited(request, bucket, *, limit, window):
    remote = str(request.META.get("REMOTE_ADDR") or "unknown")[:80]
    digest = hashlib.sha256(f"{bucket}|{remote}".encode("utf-8")).hexdigest()
    key = f"rsjc:support:rate:{digest}"
    if cache.add(key, 1, timeout=window):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:
        return False


def _device_from_request(request):
    raw = request.headers.get("X-Support-Device-Token", "").strip()
    if not raw:
        return None
    hashed = token_hash(raw)
    device = SupportDevice.objects.select_related("account").filter(token_hash=hashed, active=True, account__active=True).first()
    if not device or not secrets.compare_digest(device.token_hash, hashed):
        return None
    return device


def _touch(device, *, app_version=""):
    now = timezone.now()
    fields = ["last_seen_at"]
    device.last_seen_at = now
    if app_version and device.app_version != app_version:
        device.app_version = clean_text(app_version, 40)
        fields.append("app_version")
    device.save(update_fields=fields)
    device.account.last_seen_at = now
    device.account.save(update_fields=["last_seen_at"])


def _log_access(request, account, action, detail=None):
    SupportAccessLog.objects.create(
        account=account,
        user=request.user,
        action=safe_label(action, 60),
        detail=sanitize_detail(detail or {}),
    )
    old_ids = list(account.access_logs.values_list("id", flat=True)[500:])
    if old_ids:
        SupportAccessLog.objects.filter(id__in=old_ids).delete()


@require_GET
def api_health(request):
    return _json({"ok": True, "service": "reparossjc-support", "version": 1, "ingestEnabled": _ingest_enabled(), "time": timezone.now().isoformat()})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_bootstrap(request):
    if request.method == "OPTIONS":
        return _json({"ok": True})
    if not _ingest_enabled():
        return _json({"detail": "support ingest is not enabled"}, status=503)
    if _rate_limited(request, "bootstrap", limit=20, window=600):
        return _json({"detail": "too many bootstrap attempts"}, status=429)
    try:
        data = _json_body(request, 16_384)
        account_key = safe_identifier(data.get("accountKey"), prefix="accountKey")
        installation_id = safe_identifier(data.get("installationId"), prefix="installationId")
    except PayloadTooLarge as exc:
        return _json({"detail": str(exc)}, status=413)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    workspace_id = safe_label(data.get("workspaceId"), 100)
    current_token = request.headers.get("X-Support-Device-Token", "").strip()
    try:
        account, device, token = bootstrap_device(
            account_key=account_key,
            workspace_id=workspace_id,
            installation_id=installation_id,
            display_name=str(data.get("displayName") or "")[:160],
            device_info=data.get("device") or {},
            current_token=current_token,
        )
    except DeviceAlreadyRegistered as exc:
        return _json({"detail": str(exc), "code": "DEVICE_ALREADY_REGISTERED"}, status=409)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    return _json({
        "supportCode": account.support_code,
        "accountId": str(account.id),
        "deviceId": str(device.id),
        "deviceToken": token,
        "serverTime": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_consent(request):
    if request.method == "OPTIONS":
        return _json({"ok": True})
    if not _ingest_enabled():
        return _json({"detail": "support ingest is not enabled"}, status=503)
    device = _device_from_request(request)
    if not device:
        return _json({"detail": "invalid support device token"}, status=401)
    if _rate_limited(request, f"consent:{device.id}", limit=30, window=600):
        return _json({"detail": "too many requests"}, status=429)
    try:
        data = _json_body(request, 8_192)
    except PayloadTooLarge as exc:
        return _json({"detail": str(exc)}, status=413)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    if not isinstance(data.get("continuousSharing"), bool):
        return _json({"detail": "continuousSharing must be boolean"}, status=400)
    device.continuous_sharing = data["continuousSharing"]
    device.privacy_version = clean_text(data.get("privacyVersion") or "support-r1", 40)
    device.consent_updated_at = timezone.now()
    device.save(update_fields=["continuous_sharing", "privacy_version", "consent_updated_at", "last_seen_at"])
    _touch(device)
    return _json({"ok": True, "continuousSharing": device.continuous_sharing, "serverTime": timezone.now().isoformat()})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_events(request):
    if request.method == "OPTIONS":
        return _json({"ok": True})
    if not _ingest_enabled():
        return _json({"detail": "support ingest is not enabled"}, status=503)
    device = _device_from_request(request)
    if not device:
        return _json({"detail": "invalid support device token"}, status=401)
    if _rate_limited(request, f"events:{device.id}", limit=180, window=600):
        return _json({"detail": "too many requests"}, status=429)
    try:
        data = _json_body(request, 262_144)
    except PayloadTooLarge as exc:
        return _json({"detail": str(exc)}, status=413)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    rows = data.get("events")
    if not isinstance(rows, list):
        return _json({"detail": "events must be a list"}, status=400)
    app_version = clean_text(data.get("appVersion"), 40)
    prepared = []
    event_ids = []
    for raw in rows[:100]:
        if not isinstance(raw, dict):
            continue
        try:
            event_id = safe_identifier(raw.get("eventId"), prefix="eventId")
        except ValueError:
            continue
        action = safe_label(raw.get("action"), 100)
        entity = safe_label(raw.get("entity") or "system", 80)
        if not action:
            continue
        severity = str(raw.get("severity") or "info").lower()
        if severity not in {"info", "warn", "error"}:
            severity = "info"
        prepared.append((event_id, SupportEvent(
            account=device.account,
            device=device,
            event_id=event_id,
            occurred_at=parse_client_datetime(raw.get("occurredAt")),
            action=action,
            entity=entity,
            severity=severity,
            detail=sanitize_detail(raw.get("detail") or {}),
            app_version=app_version,
        )))
        event_ids.append(event_id)
    existing = set(SupportEvent.objects.filter(device=device, event_id__in=event_ids).values_list("event_id", flat=True))
    objects = [obj for event_id, obj in prepared if event_id not in existing]
    if objects:
        SupportEvent.objects.bulk_create(objects, batch_size=100)
    _touch(device, app_version=app_version)
    prune_device_data(device)
    return _json({"accepted": len(objects), "duplicates": len(prepared) - len(objects), "serverTime": timezone.now().isoformat()})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_snapshot(request):
    if request.method == "OPTIONS":
        return _json({"ok": True})
    if not _ingest_enabled():
        return _json({"detail": "support ingest is not enabled"}, status=503)
    device = _device_from_request(request)
    if not device:
        return _json({"detail": "invalid support device token"}, status=401)
    if _rate_limited(request, f"snapshot:{device.id}", limit=60, window=600):
        return _json({"detail": "too many requests"}, status=429)
    try:
        data = _json_body(request, 65_536)
    except PayloadTooLarge as exc:
        return _json({"detail": str(exc)}, status=413)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    clean = sanitize_snapshot(data.get("snapshot") or {})
    SupportSnapshot.objects.create(account=device.account, device=device, data=clean)
    support = clean.get("support") or {}
    if isinstance(support.get("continuousSharing"), bool):
        device.continuous_sharing = support["continuousSharing"]
        device.privacy_version = clean_text(support.get("privacyVersion") or device.privacy_version, 40)
        device.consent_updated_at = timezone.now()
        device.save(update_fields=["continuous_sharing", "privacy_version", "consent_updated_at", "last_seen_at"])
    app_version = str((clean.get("app") or {}).get("version") or "")[:40]
    _touch(device, app_version=app_version)
    prune_device_data(device)
    return _json({"ok": True, "supportCode": device.account.support_code, "serverTime": timezone.now().isoformat()})


@staff_member_required
def dashboard(request):
    q = request.GET.get("q", "").strip()
    accounts = SupportAccount.objects.prefetch_related("devices")
    if q:
        accounts = accounts.filter(support_code__icontains=q) | accounts.filter(workspace_id__icontains=q) | accounts.filter(display_name__icontains=q)
    accounts = accounts.distinct()[:60]
    return render(request, "support_center/dashboard.html", {"accounts": accounts, "q": q})


@staff_member_required
@require_POST
def offline_import(request):
    uploaded = request.FILES.get("diagnostic")
    if not uploaded:
        messages.error(request, "Selecione um pacote de diagnóstico JSON.")
        return redirect("support_center:dashboard")
    if uploaded.size > 1_048_576:
        messages.error(request, "Pacote de diagnóstico maior que 1 MB.")
        return redirect("support_center:dashboard")
    try:
        raw = uploaded.read()
        payload = json.loads(raw.decode("utf-8"))
        account, device, event_count = import_offline_package(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        messages.error(request, f"Pacote inválido: {exc}")
        return redirect("support_center:dashboard")
    _log_access(request, account, "offline_import", {"count": event_count, "status": "ok"})
    messages.success(request, f"Diagnóstico offline importado: {event_count} evento(s).")
    return redirect("support_center:account_detail", support_code=account.support_code)


@staff_member_required
def account_detail(request, support_code):
    account = get_object_or_404(SupportAccount, support_code=support_code)
    devices = list(account.devices.filter(active=True))
    latest_snapshots = {}
    for device in devices:
        snap = device.snapshots.first()
        latest_snapshots[str(device.id)] = snap.data if snap else {}
        device.latest_snapshot = snap

    diagnostic_events = list(account.events.select_related("device")[:250])
    score, findings = diagnose_account(account, devices, latest_snapshots, diagnostic_events)

    severity = str(request.GET.get("severity") or "").strip().lower()
    device_id = str(request.GET.get("device") or "").strip()
    action = str(request.GET.get("action") or "").strip()[:80]
    period = str(request.GET.get("period") or "24h").strip().lower()
    events_qs = account.events.select_related("device")
    if severity in {"info", "warn", "error"}:
        events_qs = events_qs.filter(severity=severity)
    else:
        severity = ""
    if device_id and account.devices.filter(pk=device_id).exists():
        events_qs = events_qs.filter(device_id=device_id)
    else:
        device_id = ""
    if action:
        events_qs = events_qs.filter(action__icontains=action)
    period_hours = {"24h": 24, "7d": 168, "30d": 720}.get(period)
    if period_hours:
        events_qs = events_qs.filter(occurred_at__gte=timezone.now() - timedelta(hours=period_hours))
    else:
        period = "all"
    events = list(events_qs[:500])

    _log_access(request, account, "view_account", {"count": len(events)})
    return render(request, "support_center/account.html", {
        "account": account,
        "devices": devices,
        "events": events,
        "findings": findings,
        "score": score,
        "cases": account.cases.select_related("created_by")[:30],
        "access_logs": account.access_logs.select_related("user")[:20],
        "filters": {"severity": severity, "device": device_id, "action": action, "period": period},
    })


@staff_member_required
@require_POST
def case_create(request, support_code):
    account = get_object_or_404(SupportAccount, support_code=support_code)
    title = request.POST.get("title", "").strip()[:180]
    if not title:
        messages.error(request, "Informe um título para o chamado interno.")
        return redirect("support_center:account_detail", support_code=support_code)
    case = SupportCase.objects.create(
        account=account,
        title=title,
        note=request.POST.get("note", "").strip()[:5000],
        created_by=request.user,
    )
    _log_access(request, account, "case_created", {"id": case.id, "status": case.status})
    messages.success(request, "Chamado interno criado.")
    return redirect("support_center:account_detail", support_code=support_code)


@staff_member_required
@require_POST
def case_status(request, support_code, case_id):
    account = get_object_or_404(SupportAccount, support_code=support_code)
    case = get_object_or_404(SupportCase, pk=case_id, account=account)
    status = str(request.POST.get("status") or "").strip()
    valid = {value for value, _label in SupportCase.STATUS_CHOICES}
    if status not in valid:
        messages.error(request, "Status de chamado inválido.")
        return redirect("support_center:account_detail", support_code=support_code)
    case.status = status
    case.save(update_fields=["status", "updated_at"])
    _log_access(request, account, "case_status", {"id": case.id, "status": status})
    messages.success(request, "Status do chamado atualizado.")
    return redirect("support_center:account_detail", support_code=support_code)
