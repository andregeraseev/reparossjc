from uuid import uuid4
from django.conf import settings
from django.utils import timezone
from .models import Organization, ServiceRequest

VALID_STATUSES = {key for key, _ in ServiceRequest.STATUS_CHOICES}


def new_request_id():
    return "SR" + uuid4().hex[:20]


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
    if not created:
        changed = False
        for field, value in defaults.items():
            if field == "slug" and Organization.objects.exclude(id=org.id).filter(slug=value).exists():
                continue
            if getattr(org, field) != value:
                setattr(org, field, value)
                changed = True
        if changed:
            org.save()
    return org


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
    if row is None:
        row = ServiceRequest(id=request_id, organization=org, external_request_id=external)
    elif row.id != request_id and not row.provider_local_id:
        row.provider_local_id = request_id

    existing_decision = row.client_decision
    existing_schedule = row.schedule_request
    status = str(req_payload.get("status") or row.status or "new")
    if status not in VALID_STATUSES:
        status = row.status or "new"
    row.workspace_id = str(req_payload.get("workspaceId") or row.workspace_id or getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", ""))[:80]
    row.location = req_payload.get("location") if isinstance(req_payload.get("location"), dict) else (row.location or {})
    row.requester = req_payload.get("requester") if isinstance(req_payload.get("requester"), dict) else (row.requester or {})
    row.category = str(req_payload.get("category") or row.category or "Reparos")[:120]
    row.priority = str(req_payload.get("priority") or row.priority or "Normal")[:40]
    row.description = str(req_payload.get("description") if req_payload.get("description") is not None else row.description)
    if isinstance(req_payload.get("attachments"), list):
        row.attachments = req_payload.get("attachments")
    row.status = status
    incoming_decision = str(req_payload.get("clientDecision") or "").strip()
    row.client_decision = (incoming_decision or existing_decision or "")[:40]
    if request_id and request_id != row.id:
        row.provider_local_id = request_id[:80]
    elif req_payload.get("providerLocalId"):
        row.provider_local_id = str(req_payload.get("providerLocalId"))[:80]

    if "quote" in payload:
        row.quote = payload.get("quote")
    windows = payload.get("proposedWindows")
    if isinstance(windows, list):
        row.proposed_windows = windows[:40]
    if payload.get("scheduleRequest"):
        row.schedule_request = payload.get("scheduleRequest")
    elif existing_schedule:
        row.schedule_request = existing_schedule
    if "appointment" in payload:
        row.appointment = payload.get("appointment")

    if row.appointment:
        app_status = str((row.appointment or {}).get("status") or "").lower()
        row.status = "completed" if "concl" in app_status else ("in_service" if any(x in app_status for x in ("andamento", "execu")) else "scheduled")
    elif row.schedule_request and row.status not in {"scheduled", "in_service", "completed"}:
        row.status = "schedule_requested"
    elif row.client_decision == "approved" and row.proposed_windows:
        row.status = "waiting_schedule"
    elif row.client_decision == "approved" and row.status not in {"scheduled", "in_service", "completed", "waiting_schedule", "schedule_requested"}:
        row.status = "quote_approved"
    elif row.proposed_windows and row.status in {"quote_approved", "quote_sent", "reviewing"}:
        row.status = "waiting_schedule"
    elif row.quote and str((row.quote or {}).get("status") or "").lower() in {"enviado", "sent"} and row.status in {"new", "reviewing"}:
        row.status = "quote_sent"

    existed = bool(row.pk and ServiceRequest.objects.filter(pk=row.pk).exists())
    row.server_version = (row.server_version or 1) + (1 if existed else 0)
    row.save()
    return row
