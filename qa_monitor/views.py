import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Session, Tester
from .site_auth import staff_view


MAX_BYTES = 24 * 1024
MAX_EVENTS = 160
MAX_DURATION = 24 * 60 * 60
LABELS = {
    "home": "Início", "jobs": "Atendimentos", "job": "Ficha aberta", "agenda": "Agenda",
    "quotes": "Orçamentos", "management": "Gestão", "settings": "Ajustes",
    "save_jobs": "Atendimentos", "save_clients": "Clientes", "save_quotes": "Orçamentos",
    "save_inventory": "Estoque", "save_payments": "Recebimentos", "save_expenses": "Despesas",
    "app_error": "Erro do aplicativo",
}
SCREENS = {"home", "jobs", "job", "agenda", "quotes", "management", "settings"}
SESSION_KEYS = {"protocol", "id", "device", "version", "sdk", "form", "started", "duration", "events"}


def valid_uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value, version=4)) == value
    except (ValueError, TypeError):
        return False


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def validate(data):
    if (not isinstance(data, dict) or data.keys() != SESSION_KEYS
            or not integer(data["protocol"], 1, 1) or not valid_uuid(data["id"]) or not valid_uuid(data["device"])
            or not isinstance(data["version"], str) or not re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}", data["version"])
            or not integer(data["sdk"], 28, 100) or data["form"] not in ("phone", "tablet")
            or not integer(data["started"], 1704067200, int(datetime.now().timestamp()) + 600)
            or not integer(data["duration"], 0, MAX_DURATION) or not isinstance(data["events"], list)
            or len(data["events"]) > MAX_EVENTS):
        return False
    previous = 0
    for event in data["events"]:
        required = {"step", "result", "at"}
        if not isinstance(event, dict) or event.keys() not in (required, required | {"ms"}):
            return False
        step = event["step"]
        if (not isinstance(step, str) or step not in LABELS
                or not integer(event["at"], previous, data["duration"])):
            return False
        accepted = ("opened",) if step in SCREENS else ("failed",) if step == "app_error" else ("verified", "failed")
        if "ms" in event and (not step.startswith("save_") or not integer(event["ms"], 0, 60000)):
            return False
        if event["result"] not in accepted:
            return False
        previous = event["at"]
    return True


def json_response(body, status):
    return JsonResponse(body, status=status, headers={"Cache-Control": "no-store"})


@csrf_exempt
@require_POST
def submit(request):
    if not request.is_secure():
        return json_response({"error": "https_required"}, 403)
    token = re.fullmatch(r"Bearer ([A-Za-z0-9_-]{43})", request.headers.get("Authorization", ""))
    tester = Tester.objects.filter(token_hash=hashlib.sha256(token[1].encode()).hexdigest(),
                                   enabled=True).first() if token else None
    if tester is None:
        return json_response({"error": "unauthorized"}, 401)
    length = request.META.get("CONTENT_LENGTH", "")
    if not re.fullmatch(r"[1-9][0-9]{0,5}", length) or int(length) > MAX_BYTES:
        return json_response({"error": "size"}, 413)
    if request.content_type != "application/json":
        return json_response({"error": "content_type"}, 415)
    try:
        body = request.read(int(length) + 1)
        data = json.loads(body.decode("utf-8"))
        valid = len(body) == int(length) and validate(data)
    except (ValueError, UnicodeError, RecursionError):
        valid = False
    if not valid:
        return json_response({"error": "invalid_diagnostics"}, 422)
    digest = hashlib.sha256(json.dumps(data, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    row, created = Session.objects.get_or_create(id=data["id"], defaults={
        "tester": tester, "payload": data, "digest": digest,
    })
    if row.tester_id != tester.pk or row.digest != digest:
        return json_response({"error": "session_conflict"}, 409)
    return json_response({"id": str(row.pk)}, 201 if created else 200)


def retained_sessions():
    since = timezone.now() - timedelta(days=settings.RSJC_QA_RETENTION_DAYS)
    return Session.objects.select_related("tester").filter(received_at__gte=since)


@staff_view
def dashboard(request):
    rows = retained_sessions().order_by("-received_at")
    page = Paginator(rows, 30).get_page(request.GET.get("page"))
    for row in page:
        row.results = Counter(event["result"] for event in row.payload["events"])
    return render(request, "qa_monitor/dashboard.html", {"page": page})


@staff_view
def detail(request, session_id):
    row = get_object_or_404(retained_sessions(), pk=session_id)
    events = [{**event, "label": LABELS[event["step"]]} for event in row.payload["events"]]
    return render(request, "qa_monitor/detail.html", {"row": row, "events": events})

