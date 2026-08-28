"""Support ingest extension for product/UX metadata.

This keeps the existing Support R1 consent, rate-limit and event vocabulary. R6 sends
all product signals as action=changed with detail.operation=ux_*. Only categorical
labels, bounded counters, booleans and timings are retained here.
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import views as base
from .event_policy import normalize_event_action, normalize_event_entity
from .models import SupportEvent
from .secure_ingest import ingest_mode
from .services import clean_text, parse_client_datetime, prune_device_data, safe_identifier, safe_label, sanitize_detail

_PRODUCT_LABEL_KEYS = {
    "screen", "feature", "flow", "outcome", "context", "inputMethod",
}
_PRODUCT_INT_KEYS = {
    "itemCount", "resultCount", "backtrackCount", "interactionCount",
    "renderMs", "firstActionMs", "completionMs",
}
_PRODUCT_BOOL_KEYS = {"zeroResults", "usedQuick", "usedVoice"}


def sanitize_product_detail(detail):
    """Extend the strict Support detail whitelist without allowing free text."""
    out = sanitize_detail(detail)
    if not isinstance(detail, dict):
        return out
    for key in _PRODUCT_LABEL_KEYS:
        if key in detail:
            value = safe_label(detail.get(key), 80)
            if value:
                out[key] = value
    for key in _PRODUCT_INT_KEYS:
        if key not in detail:
            continue
        try:
            value = int(detail.get(key) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        out[key] = min(86_400_000, max(0, value))
    for key in _PRODUCT_BOOL_KEYS:
        if isinstance(detail.get(key), bool):
            out[key] = detail[key]
    return out


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_events(request):
    if request.method == "OPTIONS":
        return base._json({"ok": True})
    if not base._ingest_enabled():
        return base._json({"detail": "support ingest is not enabled"}, status=503)
    device = base._device_from_request(request)
    if not device:
        return base._json({"detail": "invalid support device token"}, status=401)
    if base._rate_limited(request, f"events:{device.id}", limit=180, window=600):
        return base._json({"detail": "too many requests"}, status=429)
    try:
        data = base._json_body(request, 262_144)
        mode = ingest_mode(data, device)
    except base.PayloadTooLarge as exc:
        return base._json({"detail": str(exc)}, status=413)
    except PermissionError as exc:
        return base._json({"detail": str(exc), "code": "CONTINUOUS_SHARING_DISABLED"}, status=403)
    except ValueError as exc:
        return base._json({"detail": str(exc)}, status=400)

    rows = data.get("events")
    if not isinstance(rows, list):
        return base._json({"detail": "events must be a list"}, status=400)
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
        action = normalize_event_action(raw.get("action"))
        entity = normalize_event_entity(raw.get("entity"))
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
            detail=sanitize_product_detail(raw.get("detail") or {}),
            app_version=app_version,
        )))
        event_ids.append(event_id)

    existing = set(
        SupportEvent.objects.filter(device=device, event_id__in=event_ids)
        .values_list("event_id", flat=True)
    )
    objects = [obj for event_id, obj in prepared if event_id not in existing]
    if objects:
        SupportEvent.objects.bulk_create(objects, batch_size=100)
    base._touch(device, app_version=app_version)
    prune_device_data(device)
    return base._json({
        "accepted": len(objects),
        "duplicates": len(prepared) - len(objects),
        "mode": mode,
        "serverTime": base.timezone.now().isoformat(),
    })
