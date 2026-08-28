import json
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .diagnostics import diagnose_account
from .models import SupportAccount, SupportCase, SupportDevice, SupportEvent, SupportSnapshot
from .services import bootstrap_device, parse_client_datetime, sanitize_detail, sanitize_snapshot, token_hash


def _json_body(request):
    try:
        value = json.loads((request.body or b"{}").decode("utf-8"))
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
        device.app_version = str(app_version)[:40]
        fields.append("app_version")
    device.save(update_fields=fields)
    device.account.last_seen_at = now
    device.account.save(update_fields=["last_seen_at"])


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
    try:
        data = _json_body(request)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    workspace_id = str(data.get("workspaceId") or "").strip()[:100]
    installation_id = str(data.get("installationId") or "").strip()[:120]
    if not workspace_id or not installation_id:
        return _json({"detail": "workspaceId and installationId are required"}, status=400)
    with transaction.atomic():
        account, device, token = bootstrap_device(
            workspace_id=workspace_id,
            installation_id=installation_id,
            display_name=str(data.get("displayName") or "")[:160],
            device_info=data.get("device") or {},
        )
    return _json({
        "supportCode": account.support_code,
        "accountId": str(account.id),
        "deviceId": str(device.id),
        "deviceToken": token,
        "serverTime": timezone.now().isoformat(),
    })


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
    try:
        data = _json_body(request)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    rows = data.get("events")
    if not isinstance(rows, list):
        return _json({"detail": "events must be a list"}, status=400)
    app_version = str(data.get("appVersion") or "")[:40]
    objects = []
    for raw in rows[:100]:
        if not isinstance(raw, dict):
            continue
        event_id = str(raw.get("eventId") or "")[:120]
        action = str(raw.get("action") or "")[:100]
        if not event_id or not action:
            continue
        severity = str(raw.get("severity") or "info").lower()
        if severity not in {"info", "warn", "error"}:
            severity = "info"
        objects.append(SupportEvent(
            account=device.account,
            device=device,
            event_id=event_id,
            occurred_at=parse_client_datetime(raw.get("occurredAt")),
            action=action,
            entity=str(raw.get("entity") or "system")[:80],
            severity=severity,
            detail=sanitize_detail(raw.get("detail") or {}),
            app_version=app_version,
        ))
    SupportEvent.objects.bulk_create(objects, ignore_conflicts=True, batch_size=100)
    _touch(device, app_version=app_version)
    return _json({"accepted": len(objects), "serverTime": timezone.now().isoformat()})


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
    try:
        data = _json_body(request)
    except ValueError as exc:
        return _json({"detail": str(exc)}, status=400)
    clean = sanitize_snapshot(data.get("snapshot") or {})
    SupportSnapshot.objects.create(account=device.account, device=device, data=clean)
    old_ids = list(SupportSnapshot.objects.filter(device=device).order_by("-created_at").values_list("id", flat=True)[50:])
    if old_ids:
        SupportSnapshot.objects.filter(id__in=old_ids).delete()
    app_version = str((clean.get("app") or {}).get("version") or "")[:40]
    _touch(device, app_version=app_version)
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
def account_detail(request, support_code):
    account = get_object_or_404(SupportAccount, support_code=support_code)
    devices = list(account.devices.all())
    latest_snapshots = {}
    for device in devices:
        snap = device.snapshots.first()
        latest_snapshots[str(device.id)] = snap.data if snap else {}
        device.latest_snapshot = snap
    events = list(account.events.select_related("device")[:250])
    score, findings = diagnose_account(account, devices, latest_snapshots, events)
    return render(request, "support_center/account.html", {
        "account": account,
        "devices": devices,
        "events": events,
        "findings": findings,
        "score": score,
        "cases": account.cases.select_related("created_by")[:30],
    })


@staff_member_required
@require_POST
def case_create(request, support_code):
    account = get_object_or_404(SupportAccount, support_code=support_code)
    title = request.POST.get("title", "").strip()[:180]
    if not title:
        messages.error(request, "Informe um título para o chamado interno.")
        return redirect("support_center:account_detail", support_code=support_code)
    SupportCase.objects.create(
        account=account,
        title=title,
        note=request.POST.get("note", "").strip(),
        created_by=request.user,
    )
    messages.success(request, "Chamado interno criado.")
    return redirect("support_center:account_detail", support_code=support_code)
