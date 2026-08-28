from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import views as base
from .event_policy import normalize_event_action, normalize_event_entity
from .models import SupportEvent
from .services import clean_text, parse_client_datetime, prune_device_data, safe_identifier, sanitize_detail


def ingest_mode(data, device):
    """Return manual/continuous and enforce server-side consent for background telemetry.

    Missing mode is treated as manual for backward compatibility with Review3 and older
    clients. A future or buggy client cannot use the continuous channel while the server's
    per-device consent flag is off.
    """
    mode = str(data.get("mode") or "manual").strip().lower()
    if mode not in {"manual", "continuous"}:
        raise ValueError("invalid support ingest mode")
    if mode == "continuous" and not device.continuous_sharing:
        raise PermissionError("continuous support sharing is not enabled")
    return mode


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
            detail=sanitize_detail(raw.get("detail") or {}),
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
