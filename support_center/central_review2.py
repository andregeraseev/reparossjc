from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from . import views as base
from .diagnostics import diagnose_account, diagnose_device, select_primary_device
from .models import SupportAccount


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def group_events(events):
    grouped = {}
    for event in events:
        detail = event.detail or {}
        marker = str(detail.get("code") or detail.get("httpStatus") or detail.get("stackSignature") or "")[:100]
        key = (str(event.device_id), event.severity, event.action, event.entity, marker)
        row = grouped.get(key)
        if row is None:
            grouped[key] = {
                "device": event.device,
                "severity": event.severity,
                "action": event.action,
                "entity": event.entity,
                "marker": marker,
                "count": 1,
                "first_at": event.occurred_at,
                "last_at": event.occurred_at,
            }
            continue
        row["count"] += 1
        row["first_at"] = min(row["first_at"], event.occurred_at)
        row["last_at"] = max(row["last_at"], event.occurred_at)
    rows = [row for row in grouped.values() if row["count"] >= 2]
    rows.sort(key=lambda row: (row["last_at"], row["count"]), reverse=True)
    return rows[:20]


def technical_summary(account, primary, score, findings, latest_snapshots, recent_events):
    lines = [f"{account.support_code} • Saúde {score}/100"]
    if primary:
        label = f"{primary.manufacturer} {primary.model}".strip() or "aparelho"
        lines.append(f"Fonte atual: {label} • app {primary.app_version or '-'} • Android {primary.android_release or '-'}")
        snap = latest_snapshots.get(str(primary.id)) or {}
        sync = snap.get("sync") or {}
        backup = snap.get("backup") or {}
        lines.append(f"Fila: {_safe_int(sync.get('pendingCount'))} pendente(s) • backup: {backup.get('lastBackupAt') or 'não informado'}")
        error_code = str(sync.get("corporateLastErrorCode") or "").strip()
        if error_code:
            lines.append(f"Corporate: {error_code}")
        errors = [event for event in recent_events if event.device_id == primary.id and event.severity == "error"]
        if errors:
            latest = errors[0]
            detail = latest.detail or {}
            marker = detail.get("code") or detail.get("httpStatus") or detail.get("stackSignature") or "sem código"
            lines.append(f"Último erro: {latest.action} • {marker}")
    if findings:
        lines.append("Prioridade: " + " | ".join(f"{item['code']}: {item['title']}" for item in findings[:3]))
    else:
        lines.append("Prioridade: nenhum alerta técnico conhecido")
    return "\n".join(lines)


@never_cache
def dashboard(request):
    return base.dashboard(request)


@never_cache
def offline_import(request):
    return base.offline_import(request)


@staff_member_required
@never_cache
def account_detail(request, support_code):
    account = get_object_or_404(SupportAccount, support_code=support_code)
    devices = list(account.devices.filter(active=True))
    latest_snapshots = {}
    for device in devices:
        snap = device.snapshots.first()
        latest_snapshots[str(device.id)] = snap.data if snap else {}
        device.latest_snapshot = snap

    diagnostic_events = list(account.events.select_related("device")[:500])
    score, findings = diagnose_account(account, devices, latest_snapshots, diagnostic_events)
    primary = select_primary_device(devices)
    for device in devices:
        device_events = [event for event in diagnostic_events if event.device_id == device.id]
        device.support_score, device.support_findings = diagnose_device(
            device,
            latest_snapshots.get(str(device.id)) or {},
            device_events,
        )
        device.is_primary_support_device = primary is not None and device.id == primary.id

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

    base._log_access(request, account, "view_account", {"count": len(events)})
    return render(request, "support_center/account.html", {
        "account": account,
        "devices": devices,
        "primary_device": primary,
        "events": events,
        "event_groups": group_events(diagnostic_events),
        "technical_summary": technical_summary(account, primary, score, findings, latest_snapshots, diagnostic_events),
        "findings": findings,
        "score": score,
        "cases": account.cases.select_related("created_by")[:30],
        "access_logs": account.access_logs.select_related("user")[:20],
        "filters": {"severity": severity, "device": device_id, "action": action, "period": period},
    })
