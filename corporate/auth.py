import hmac
import hashlib
from functools import wraps
from django.conf import settings
from django.http import HttpResponse, JsonResponse

from .models import ServiceProvider


def _bearer(request):
    raw = request.headers.get("Authorization", "")
    if not raw.lower().startswith("bearer "):
        return ""
    return raw.split(" ", 1)[1].strip()


def _with_operator_cors(response):
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Workspace-ID, X-User-ID"
    response["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
    response["Access-Control-Expose-Headers"] = "Content-Disposition, Content-Length"
    response["Access-Control-Max-Age"] = "600"
    return response


def operator_api_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        # WebView/file origins perform a preflight before requests carrying
        # Authorization/X-Workspace-ID. Preflight contains no bearer token.
        if request.method == "OPTIONS":
            return _with_operator_cors(HttpResponse(status=204))

        workspace_id = request.headers.get("X-Workspace-ID", "").strip() or getattr(
            settings, "CORPORATE_DEFAULT_WORKSPACE_ID", ""
        )
        if not workspace_id:
            return _with_operator_cors(JsonResponse({"detail": "workspace is required"}, status=400))

        provider = ServiceProvider.objects.filter(workspace_id=workspace_id, active=True).first()
        supplied = _bearer(request)
        authorized = False
        if provider and provider.operator_token_hash:
            supplied_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest() if supplied else ""
            authorized = bool(supplied_hash) and hmac.compare_digest(supplied_hash, provider.operator_token_hash)
        elif workspace_id == getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", ""):
            # Backward compatibility for the existing Reparos SJC installation.
            # New providers must always use an individual hashed token.
            expected = getattr(settings, "CORPORATE_OPERATOR_TOKEN", "") or ""
            if not expected:
                return _with_operator_cors(JsonResponse({"detail": "operator API token is not configured"}, status=503))
            authorized = bool(supplied) and hmac.compare_digest(supplied, expected)
        elif provider:
            return _with_operator_cors(JsonResponse({"detail": "provider token is not configured"}, status=503))

        if not authorized:
            return _with_operator_cors(JsonResponse({"detail": "unauthorized"}, status=401))
        request.corporate_workspace_id = workspace_id
        request.corporate_provider = provider
        return _with_operator_cors(view(request, *args, **kwargs))

    return wrapped
