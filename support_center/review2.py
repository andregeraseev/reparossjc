from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import views as base
from .models import SupportSnapshot
from .secure_ingest import ingest_mode
from .services import clean_text, prune_device_data, sanitize_snapshot


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_snapshot(request):
    """Snapshot endpoint whose telemetry can never mutate consent state."""
    if request.method == "OPTIONS":
        return base._json({"ok": True})
    if not base._ingest_enabled():
        return base._json({"detail": "support ingest is not enabled"}, status=503)
    device = base._device_from_request(request)
    if not device:
        return base._json({"detail": "invalid support device token"}, status=401)
    if base._rate_limited(request, f"snapshot:{device.id}", limit=60, window=600):
        return base._json({"detail": "too many requests"}, status=429)
    try:
        data = base._json_body(request, 65_536)
        mode = ingest_mode(data, device)
    except base.PayloadTooLarge as exc:
        return base._json({"detail": str(exc)}, status=413)
    except PermissionError as exc:
        return base._json({"detail": str(exc), "code": "CONTINUOUS_SHARING_DISABLED"}, status=403)
    except ValueError as exc:
        return base._json({"detail": str(exc)}, status=400)

    clean = sanitize_snapshot(data.get("snapshot") or {})
    SupportSnapshot.objects.create(account=device.account, device=device, data=clean)
    app_version = clean_text((clean.get("app") or {}).get("version"), 40)
    base._touch(device, app_version=app_version)
    prune_device_data(device)
    return base._json({
        "ok": True,
        "mode": mode,
        "supportCode": device.account.support_code,
        "serverTime": base.timezone.now().isoformat(),
    })
