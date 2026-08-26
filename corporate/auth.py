import hmac
from functools import wraps
from django.conf import settings
from django.http import JsonResponse


def _bearer(request):
    raw = request.headers.get("Authorization", "")
    if not raw.lower().startswith("bearer "):
        return ""
    return raw.split(" ", 1)[1].strip()


def operator_api_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        expected = getattr(settings, "CORPORATE_OPERATOR_TOKEN", "") or ""
        supplied = _bearer(request)
        if not expected:
            return JsonResponse({"detail": "operator API token is not configured"}, status=503)
        if not supplied or not hmac.compare_digest(supplied, expected):
            return JsonResponse({"detail": "unauthorized"}, status=401)
        return view(request, *args, **kwargs)

    return wrapped
