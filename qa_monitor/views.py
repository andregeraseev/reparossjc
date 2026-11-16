import base64
import binascii
import hashlib
import io
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import BugReport, Session, Tester
from .site_auth import staff_view
from .trace import LABELS, LIMITS, MAX_DURATION, SCREENS, event_rows, events_valid, integer


MAX_BYTES = 64 * 1024
LEGACY_MAX_BYTES = 24 * 1024
BUG_BYTES = 320 * 1024
SCREENSHOT_BYTES = 220 * 1024
BUG_KEYS = {"id", "version", "sdk", "screen", "description", "session", "events", "screenshot"}
SESSION_KEYS = {"protocol", "id", "device", "version", "sdk", "form", "started", "duration", "events"}


def valid_uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value, version=4)) == value
    except (ValueError, TypeError):
        return False


def app_metadata(data):
    return (isinstance(data["version"], str) and re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}", data["version"])
            and integer(data["sdk"], 28, 100))


def validate(data):
    return (isinstance(data, dict) and data.keys() == SESSION_KEYS
            and integer(data["protocol"], 1, 2) and valid_uuid(data["id"]) and valid_uuid(data["device"])
            and app_metadata(data) and data["form"] in ("phone", "tablet")
            and integer(data["started"], 1704067200, int(datetime.now().timestamp()) + 600)
            and integer(data["duration"], 0, MAX_DURATION)
            and events_valid(data["events"], data["protocol"], LIMITS[data["protocol"]], data["duration"]))


def decode_screenshot(value):
    if not isinstance(value, str):
        raise ValueError("screenshot")
    try:
        raw = base64.b64decode(value, validate=True)
    except binascii.Error as error:
        raise ValueError("screenshot") from error
    if not raw:
        return raw
    if len(raw) > SCREENSHOT_BYTES:
        raise ValueError("screenshot")
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(raw), formats=["JPEG"]) as image:
            if not (1 <= image.width <= 1280 and 1 <= image.height <= 1280):
                raise ValueError("screenshot")
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("screenshot") from error
    return raw


def json_response(body, status):
    return JsonResponse(body, status=status, headers={"Cache-Control": "no-store"})


def read_submission(request, max_bytes):
    if not request.is_secure():
        return None, None, json_response({"error": "https_required"}, 403)
    token = re.fullmatch(r"Bearer ([A-Za-z0-9_-]{43})", request.headers.get("Authorization", ""))
    tester = Tester.objects.filter(token_hash=hashlib.sha256(token[1].encode()).hexdigest(),
                                   enabled=True).first() if token else None
    if tester is None:
        return None, None, json_response({"error": "unauthorized"}, 401)
    length = request.META.get("CONTENT_LENGTH", "")
    if not re.fullmatch(r"[1-9][0-9]{0,5}", length) or int(length) > max_bytes:
        return None, None, json_response({"error": "size"}, 413)
    if request.content_type != "application/json":
        return None, None, json_response({"error": "content_type"}, 415)
    try:
        body = request.read(int(length) + 1)
        if len(body) == int(length):
            return tester, json.loads(body.decode("utf-8")), None
    except (ValueError, UnicodeError, RecursionError):
        pass
    return None, None, json_response({"error": "invalid_diagnostics"}, 422)


@csrf_exempt
@require_POST
def submit(request):
    tester, data, error = read_submission(request, MAX_BYTES)
    if error is not None:
        return error
    if not validate(data):
        return json_response({"error": "invalid_diagnostics"}, 422)
    if data["protocol"] == 1 and int(request.META["CONTENT_LENGTH"]) > LEGACY_MAX_BYTES:
        return json_response({"error": "size"}, 413)
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
    events = event_rows(row.payload["events"])
    return render(request, "qa_monitor/detail.html", {"row": row, "events": events})



@csrf_exempt
@require_POST
def submit_bug(request):
    tester, data, error = read_submission(request, BUG_BYTES)
    if error is not None:
        return error
    if (not isinstance(data, dict) or data.keys() != BUG_KEYS or not valid_uuid(data["id"])
            or not app_metadata(data) or not isinstance(data["screen"], str) or data["screen"] not in SCREENS
            or not isinstance(data["description"], str) or not 1 <= len(data["description"].strip()) <= 1200
            or not (data["session"] == "" or valid_uuid(data["session"]))
            or not events_valid(data["events"], 2, 30) or (not data["session"] and data["events"])):
        return json_response({"error": "invalid_report"}, 422)
    try:
        screenshot = decode_screenshot(data["screenshot"])
    except ValueError:
        return json_response({"error": "invalid_screenshot"}, 422)
    digest = hashlib.sha256(json.dumps(data, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    data.pop("screenshot")
    row, created = BugReport.objects.get_or_create(id=data["id"], defaults={
        "tester": tester, "payload": data, "digest": digest, "screenshot": screenshot,
    })
    if row.tester_id != tester.pk or row.digest != digest:
        return json_response({"error": "report_conflict"}, 409)
    return json_response({"id": str(row.pk)}, 201 if created else 200)


def retained_bugs():
    since = timezone.now() - timedelta(days=settings.RSJC_QA_RETENTION_DAYS)
    return BugReport.objects.select_related("tester").filter(received_at__gte=since)


@staff_view
def bugs(request):
    rows = retained_bugs().defer("screenshot").order_by("-received_at")
    page = Paginator(rows, 30).get_page(request.GET.get("page"))
    for row in page:
        row.screen = LABELS[row.payload["screen"]]
    return render(request, "qa_monitor/bugs.html", {"page": page})


@staff_view
def bug_detail(request, report_id):
    row = get_object_or_404(retained_bugs(), pk=report_id)
    session = (retained_sessions().filter(pk=row.payload["session"], tester=row.tester).first()
               if row.payload["session"] else None)
    return render(request, "qa_monitor/bug_detail.html", {
        "row": row, "screen": LABELS[row.payload["screen"]], "events": event_rows(row.payload["events"]),
        "session": session,
    })


@staff_view
def bug_screenshot(request, report_id):
    row = get_object_or_404(retained_bugs(), pk=report_id)
    if not row.screenshot:
        raise Http404
    return HttpResponse(bytes(row.screenshot), content_type="image/jpeg", headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
    })
