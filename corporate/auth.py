import hmac
from functools import wraps
from django.conf import settings
from django.http import HttpResponse, JsonResponse


def _bearer(request):
    raw = request.headers.get("Authorization", "")
    if not raw.lower().startswith("bearer "):
        return ""
    return raw.split(" ", 1)[1].strip()


def _with_operator_cors(response):
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Workspace-ID, X-User-ID"
    response["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
    response["Access-Control-Max-Age"] = "600"
    return response


def operator_api_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        # WebView/file origins perform a preflight before requests carrying
        # Authorization/X-Workspace-ID. Preflight contains no bearer token.
        if request.method == "OPTIONS":
            return _with_operator_cors(HttpResponse(status=204))

        expected = getattr(settings, "CORPORATE_OPERATOR_TOKEN", "") or ""
        supplied = _bearer(request)
        if not expected:
            return _with_operator_cors(JsonResponse({"detail": "operator API token is not configured"}, status=503))
        if not supplied or not hmac.compare_digest(supplied, expected):
            return _with_operator_cors(JsonResponse({"detail": "unauthorized"}, status=401))
        return _with_operator_cors(view(request, *args, **kwargs))

    return wrapped
