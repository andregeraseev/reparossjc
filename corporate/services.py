from datetime import datetime
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from .models import AvailabilitySnapshot, Organization, ServiceRequest

VALID_STATUSES = {key for key, _ in ServiceRequest.STATUS_CHOICES}
CLOSED_STATUSES = {"completed", "rejected", "cancelled"}
PORTAL_DECISIONS = {"approved", "schedule_selected"}


class ConflictError(ValueError):
    """Raised when the operator is trying to write an outdated request."""


def new_request_id():
    return "SR" + uuid4().hex[:20]


def window_key(window):
    window = window or {}
    return (
        str(window.get("sourceId") or ""),
        str(window.get("date") or ""),
        str(window.get("start") or ""),
        str(window.get("end") or ""),
    )


def window_is_future(window, *, at=None):
    """Only expose slots whose start is still in the future in São Paulo time."""
    window = window or {}
    date = str(window.get("date") or "").strip()
    start = str(window.get("start") or "").strip()
    end = str(window.get("end") or "").strip()
    if not date or not start or not end:
        return False
    try:
        naive = datetime.fromisoformat(f"{date}T{start}:00")
        aware = timezone.make_aware(naive, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return False
    return aware > (at or timezone.now())


def public_window(window):
    return {
        "sourceId": str((window or {}).get("sourceId") or ""),
        "date": str((window or {}).get("date") or ""),
        "start": str((window or {}).get("start") or ""),
        "end": str((window or {}).get("end") or ""),
    }


def normalize_public_windows(windows, *, limit=100, require_future=True):
    out = []
    seen = set()
    for raw in (windows or [])[:limit]:
        if not isinstance(raw, dict):
            continue
        item = public_window(raw)
        key = window_key(item)
        if not all(key[1:]):
            continue
        if require_future and not window_is_future(item):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def public_organization(org):
    return {"id": org.id, "slug": org.slug, "name": org.name, "displayName": org.display_name, "demo": org.demo}


def public_request(row):
    return {
        "id": row.id,
        "externalRequestId": row.external_request_id,
        "organizationId": row.organization_id,
        "organizationName": row.organization.display_name,
        "workspaceId": row.workspace_id,
        "location": row.location or {},
        "requester": row.requester or {},
        "category": row.category,
        "priority": row.priority,
        "description": row.description,
        "attachments": row.attachments or [],
        "status": row.status,
        "clientDecision": row.client_decision,
        "providerLocalId": row.provider_local_id,
        "proposedWindows": row.proposed_windows or [],
        "scheduleRequest": row.schedule_request,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
        "_serverVersion": row.server_version,
    }


def contract_for(row):
    return {
        "format": "ReparosSJC_Corporate_Request",
        "version": 1,
        "generatedAt": timezone.now().isoformat(),
        "organization": public_organization(row.organization),
        "serviceRequest": public_request(row),
        "quote": row.quote,
        "proposedWindows": row.proposed_windows or [],
        "scheduleRequest": row.schedule_request,
        "appointment": row.appointment,
    }


def get_or_create_org(payload):
    org_id = str(payload.get("id") or "").strip()
    if not org_id:
        raise ValueError("organization.id is required")
    defaults = {
        "slug": str(payload.get("slug") or org_id).strip().lower()[:80],
        "name": str(payload.get("name") or payload.get("displayName") or "Empresa")[:160],
        "display_name": str(payload.get("displayName") or payload.get("name") or "Empresa")[:160],
        "demo": bool(payload.get("demo", False)),
        "active": True,
    }
    org, created = Organization.objects.get_or_create(id=org_id, defaults=defaults)
    if created:
        return org

    # Slug/demo/active are server-owned identity fields. An old or offline app must
    # never turn a production organization back into a demo organization.
    changed = False
    for field in ("name", "display_name"):
        value = defaults[field]
        if value and getattr(org, field) != value:
            setattr(org, field, value)
            changed = True
    if changed:
        org.save(update_fields=["name", "display_name", "updated_at"])
    return org


def _incoming_schedule(payload, req_payload):
    if "scheduleRequest" in payload:
        return True, payload.get("scheduleRequest")
    if "scheduleRequest" in req_payload:
        return True, req_payload.get("scheduleRequest")
    return False, None


def _incoming_windows(payload, req_payload):
    if "proposedWindows" in payload:
        return payload.get("proposedWindows")
    if "proposedWindows" in req_payload:
        return req_payload.get("proposedWindows")
    return None


def _validate_offered_windows(workspace_id, windows):
    normalized = normalize_public_windows(windows, limit=12, require_future=True)
    if windows and not normalized:
        raise ValueError("Nenhum horário oferecido continua válido")
    if not normalized:
        return []
    snap = AvailabilitySnapshot.objects.filter(pk=workspace_id).first()
    if snap is None:
        raise ValueError("Publique a disponibilidade antes de oferecer horários")
    available = {window_key(w) for w in normalize_public_windows(snap.windows, limit=100, require_future=True)}
    invalid = [w for w in normalized if window_key(w) not in available]
    if invalid:
        raise ConflictError("Um ou mais horários não estão mais disponíveis. Atualize e escolha novamente.")
    return normalized


def upsert_from_contract(payload):
    if payload.get("format") != "ReparosSJC_Corporate_Request" or int(payload.get("version") or 0) != 1:
        raise ValueError("invalid corporate contract")
    org_payload = payload.get("organization") or {}
    req_payload = payload.get("serviceRequest") or {}
    org = get_or_create_org(org_payload)
    external = str(req_payload.get("externalRequestId") or "").strip()
    if not external:
        raise ValueError("serviceRequest.externalRequestId is required")
    request_id = str(req_payload.get("id") or "").strip() or new_request_id()
    row = ServiceRequest.objects.filter(organization=org, external_request_id=external).first()
    existed = row is not None
    if row is None:
        row = ServiceRequest(id=request_id, organization=org, external_request_id=external)
    elif row.id != request_id and not row.provider_local_id:
        row.provider_local_id = request_id[:80]

    incoming_version = int(req_payload.get("_serverVersion") or 0)
    if existed and incoming_version and incoming_version != row.server_version:
        raise ConflictError("Chamado atualizado no servidor. Atualize e tente novamente.")

    existing_status = row.status
    existing_decision = row.client_decision
    existing_schedule = row.schedule_request
    incoming_status = str(req_payload.get("status") or existing_status or "new")
    if incoming_status not in VALID_STATUSES:
        incoming_status = existing_status or "new"
    incoming_decision = str(req_payload.get("clientDecision") or "").strip()
    schedule_present, incoming_schedule = _incoming_schedule(payload, req_payload)

    row.workspace_id = str(req_payload.get("workspaceId") or row.workspace_id or getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", ""))[:80]
    if not row.workspace_id:
        raise ValueError("workspaceId is required")
    row.location = req_payload.get("location") if isinstance(req_payload.get("location"), dict) else (row.location or {})
    row.requester = req_payload.get("requester") if isinstance(req_payload.get("requester"), dict) else (row.requester or {})
    row.category = str(req_payload.get("category") or row.category or "Reparos")[:120]
    row.priority = str(req_payload.get("priority") or row.priority or "Normal")[:40]
    row.description = str(req_payload.get("description") if req_payload.get("description") is not None else row.description)
    if isinstance(req_payload.get("attachments"), list):
        row.attachments = req_payload.get("attachments")
    if request_id and request_id != row.id:
        row.provider_local_id = request_id[:80]
    elif req_payload.get("providerLocalId"):
        row.provider_local_id = str(req_payload.get("providerLocalId"))[:80]

    if "quote" in payload:
        row.quote = payload.get("quote")

    # Portal owns approval and slot selection. The provider may only reset a
    # schedule_selected decision when it is explicitly rejecting a stale slot.
    clearing_schedule = bool(
        existed
        and existing_schedule
        and schedule_present
        and incoming_schedule is None
        and incoming_decision == "approved"
        and incoming_status in {"quote_approved", "waiting_schedule"}
    )
    if existing_decision in PORTAL_DECISIONS:
        row.client_decision = "approved" if clearing_schedule else existing_decision
    else:
        row.client_decision = (incoming_decision or existing_decision or "")[:40]

    windows = _incoming_windows(payload, req_payload)
    if isinstance(windows, list) and not (existing_schedule and not clearing_schedule):
        row.proposed_windows = _validate_offered_windows(row.workspace_id, windows) if windows else []

    if schedule_present:
        if clearing_schedule:
            row.schedule_request = None
        elif existing_schedule:
            row.schedule_request = existing_schedule
        # An operator cannot invent a client's schedule choice.
    elif existing_schedule:
        row.schedule_request = existing_schedule

    if "appointment" in payload:
        row.appointment = payload.get("appointment")

    # Server-side transition rules. The portal owns decision states; the app owns
    # quote/availability/appointment progression.
    if row.appointment:
        app_status = str((row.appointment or {}).get("status") or "").lower()
        row.status = "completed" if "concl" in app_status else ("in_service" if any(x in app_status for x in ("andamento", "execu")) else "scheduled")
    elif row.schedule_request:
        row.status = "schedule_requested"
    elif row.client_decision == "approved" and row.proposed_windows:
        row.status = "waiting_schedule"
    elif row.client_decision == "approved":
        row.status = "quote_approved"
    elif row.quote and str((row.quote or {}).get("status") or "").lower() in {"enviado", "sent"}:
        row.status = "quote_sent"
    elif existing_status in CLOSED_STATUSES:
        row.status = existing_status
    elif incoming_status in {"new", "reviewing", "waiting_information"}:
        row.status = incoming_status
    else:
        row.status = existing_status or "new"

    row.server_version = (row.server_version or 1) + (1 if existed else 0)
    row.save()
    return row
