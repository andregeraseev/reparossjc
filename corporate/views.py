import json
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import operator_api_required
from .models import AvailabilitySnapshot, PartnerMembership, ServiceRequest
from .services import (
    ConflictError,
    contract_for,
    new_request_id,
    normalize_public_windows,
    upsert_from_contract,
    window_is_future,
    window_key,
)


def _json_body(request):
    try:
        return json.loads((request.body or b"{}").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid JSON")


def _membership(request):
    return PartnerMembership.objects.select_related("organization").filter(user=request.user, active=True, organization__active=True).first()


def _reserved_window_keys(workspace_id, exclude_request_id=None):
    qs = ServiceRequest.objects.filter(
        workspace_id=workspace_id,
        status__in=("schedule_requested", "scheduled", "in_service"),
        schedule_request__isnull=False,
    )
    if exclude_request_id:
        qs = qs.exclude(pk=exclude_request_id)
    return {window_key(row.schedule_request) for row in qs.only("schedule_request") if row.schedule_request}


@require_GET
def health(request):
    return JsonResponse({"ok": True, "service": "reparossjc-corporate", "version": 1, "time": timezone.now().isoformat()})


@csrf_exempt
@operator_api_required
def operator_requests(request):
    if request.method == "GET":
        qs = ServiceRequest.objects.select_related("organization").all()
        workspace = request.GET.get("workspace_id", "").strip()
        if workspace:
            qs = qs.filter(workspace_id=workspace)
        updated_after = request.GET.get("updated_after", "").strip()
        if updated_after:
            try:
                dt = datetime.fromisoformat(updated_after.replace("Z", "+00:00"))
                qs = qs.filter(updated_at__gt=dt)
            except ValueError:
                return JsonResponse({"detail": "updated_after must be ISO-8601"}, status=400)
        return JsonResponse({"requests": [contract_for(row) for row in qs[:250]], "serverTime": timezone.now().isoformat()})
    if request.method == "POST":
        try:
            payload = _json_body(request)
            with transaction.atomic():
                row = upsert_from_contract(payload)
            return JsonResponse(contract_for(row))
        except ConflictError as exc:
            return JsonResponse({"detail": str(exc)}, status=409)
        except ValueError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse({"detail": "method not allowed"}, status=405)


@csrf_exempt
@operator_api_required
def operator_request_detail(request, request_id):
    row = get_object_or_404(ServiceRequest.objects.select_related("organization"), pk=request_id)
    if request.method == "GET":
        return JsonResponse(contract_for(row))
    if request.method in {"PUT", "POST"}:
        try:
            payload = _json_body(request)
            with transaction.atomic():
                updated = upsert_from_contract(payload)
            return JsonResponse(contract_for(updated))
        except ConflictError as exc:
            return JsonResponse({"detail": str(exc)}, status=409)
        except ValueError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse({"detail": "method not allowed"}, status=405)


@csrf_exempt
@operator_api_required
def operator_availability(request):
    workspace_id = request.headers.get("X-Workspace-ID", "").strip() or getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", "")
    if not workspace_id:
        return JsonResponse({"detail": "workspace is required"}, status=400)
    if request.method == "GET":
        snap = AvailabilitySnapshot.objects.filter(pk=workspace_id).first()
        windows = normalize_public_windows(snap.windows if snap else [], limit=100, require_future=True)
        return JsonResponse({"workspaceId": workspace_id, "version": snap.version if snap else 0, "windows": windows, "updatedAt": snap.updated_at.isoformat() if snap else ""})
    if request.method == "POST":
        try:
            payload = _json_body(request)
        except ValueError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
        windows = payload.get("windows")
        if not isinstance(windows, list):
            return JsonResponse({"detail": "windows must be a list"}, status=400)

        with transaction.atomic():
            reserved = _reserved_window_keys(workspace_id)
            public_windows = [
                w
                for w in normalize_public_windows(windows, limit=100, require_future=True)
                if window_key(w) not in reserved
            ]
            snap, created = AvailabilitySnapshot.objects.select_for_update().get_or_create(
                workspace_id=workspace_id,
                defaults={"windows": public_windows, "version": 1},
            )
            if not created and snap.windows != public_windows:
                snap.windows = public_windows
                snap.version += 1
                snap.save(update_fields=["windows", "version", "updated_at"])

            # Global availability is only the safe source. It never adds options to
            # a request. For requests already waiting, it may only remove offers
            # that are no longer available/reserved.
            available_keys = {window_key(w) for w in public_windows}
            waiting = ServiceRequest.objects.select_for_update().filter(
                workspace_id=workspace_id,
                status="waiting_schedule",
                client_decision="approved",
                schedule_request__isnull=True,
            )
            for row in waiting:
                next_offered = [w for w in (row.proposed_windows or []) if window_key(w) in available_keys and window_is_future(w)]
                if row.proposed_windows != next_offered:
                    row.proposed_windows = next_offered
                    row.server_version += 1
                    row.save(update_fields=["proposed_windows", "server_version", "updated_at"])

        return JsonResponse({"workspaceId": workspace_id, "version": snap.version, "windows": snap.windows, "updatedAt": snap.updated_at.isoformat()})
    return JsonResponse({"detail": "method not allowed"}, status=405)


class CorporateLoginView(LoginView):
    template_name = "corporate/login.html"
    redirect_authenticated_user = True


class CorporateLogoutView(LogoutView):
    next_page = reverse_lazy("corporate:login")


@login_required
def portal_home(request):
    membership = _membership(request)
    if not membership:
        return render(request, "corporate/no_access.html", status=403)
    rows = ServiceRequest.objects.filter(organization=membership.organization).select_related("organization")[:100]
    return render(request, "corporate/portal.html", {"membership": membership, "organization": membership.organization, "requests": rows})


@login_required
@require_POST
def portal_create(request):
    membership = _membership(request)
    if not membership:
        return JsonResponse({"detail": "forbidden"}, status=403)
    org = membership.organization
    external = request.POST.get("external_request_id", "").strip()
    if not external:
        external = f"{org.slug.upper()[:12]}-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}"
    if ServiceRequest.objects.filter(organization=org, external_request_id=external).exists():
        messages.error(request, "Já existe um chamado com esse número.")
        return redirect("corporate:portal")
    location_label = request.POST.get("location", "").strip()
    row = ServiceRequest.objects.create(
        id=new_request_id(),
        external_request_id=external[:120],
        organization=org,
        workspace_id=getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", ""),
        location={"label": location_label, "address": request.POST.get("address", "").strip()},
        requester={
            "name": request.POST.get("requester_name", "").strip() or request.user.get_full_name() or request.user.username,
            "phone": request.POST.get("requester_phone", "").strip(),
            "email": request.user.email or "",
        },
        category=request.POST.get("category", "").strip() or "Manutenção",
        priority=request.POST.get("priority", "").strip() or "Normal",
        description=request.POST.get("description", "").strip(),
        status="new",
    )
    messages.success(request, f"Chamado {row.external_request_id} enviado para a Reparos SJC.")
    return redirect("corporate:portal")


@login_required
@require_POST
def portal_approve(request, request_id):
    membership = _membership(request)
    if not membership:
        return JsonResponse({"detail": "forbidden"}, status=403)
    with transaction.atomic():
        row = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, organization=membership.organization)
        if not row.quote:
            return HttpResponseBadRequest("Orçamento ainda não disponível")
        if row.status in {"scheduled", "in_service", "completed", "cancelled", "rejected"}:
            messages.error(request, "Esse chamado não pode mais ser aprovado nesta etapa.")
            return redirect("corporate:portal")
        row.client_decision = "approved"
        row.status = "quote_approved"
        row.proposed_windows = []
        row.server_version += 1
        row.save(update_fields=["client_decision", "status", "proposed_windows", "server_version", "updated_at"])
    messages.success(request, "Orçamento aprovado. Aguardando a Reparos SJC oferecer horários.")
    return redirect("corporate:portal")


@login_required
@require_POST
def portal_schedule(request, request_id):
    membership = _membership(request)
    if not membership:
        return JsonResponse({"detail": "forbidden"}, status=403)
    source_id = request.POST.get("source_id", "").strip()

    with transaction.atomic():
        row = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, organization=membership.organization)
        if row.status != "waiting_schedule" or row.client_decision != "approved" or row.schedule_request:
            messages.error(request, "Esse chamado não está aguardando escolha de horário.")
            return redirect("corporate:portal")
        chosen = next((w for w in (row.proposed_windows or []) if str(w.get("sourceId") or "") == source_id), None)
        if not chosen or not window_is_future(chosen):
            messages.error(request, "Esse horário não está mais disponível. Escolha outra opção.")
            return redirect("corporate:portal")

        snap = AvailabilitySnapshot.objects.select_for_update().filter(pk=row.workspace_id or getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", "")).first()
        if snap is None or window_key(chosen) not in {window_key(w) for w in normalize_public_windows(snap.windows, limit=100, require_future=True)}:
            messages.error(request, "Esse horário acabou de ficar indisponível. Escolha outra opção.")
            return redirect("corporate:portal")

        conflict = ServiceRequest.objects.select_for_update().filter(
            workspace_id=row.workspace_id,
            status__in=("schedule_requested", "scheduled", "in_service"),
            schedule_request__isnull=False,
        ).exclude(pk=row.pk)
        if any(window_key(other.schedule_request) == window_key(chosen) for other in conflict):
            messages.error(request, "Esse horário acabou de ser reservado por outro atendimento. Escolha outra opção.")
            return redirect("corporate:portal")

        row.schedule_request = {
            "sourceId": str(chosen.get("sourceId") or ""),
            "date": str(chosen.get("date") or ""),
            "start": str(chosen.get("start") or ""),
            "end": str(chosen.get("end") or ""),
        }
        row.client_decision = "schedule_selected"
        row.status = "schedule_requested"
        row.server_version += 1
        row.save(update_fields=["schedule_request", "client_decision", "status", "server_version", "updated_at"])

        # Reserve immediately on the server. The provider's next availability
        # publication is also filtered against active reservations, so the slot
        # cannot be reintroduced before the app confirms the appointment.
        chosen_key = window_key(chosen)
        next_snapshot = [w for w in normalize_public_windows(snap.windows, limit=100, require_future=True) if window_key(w) != chosen_key]
        if snap.windows != next_snapshot:
            snap.windows = next_snapshot
            snap.version += 1
            snap.save(update_fields=["windows", "version", "updated_at"])

        others = ServiceRequest.objects.select_for_update().filter(
            workspace_id=row.workspace_id,
            status="waiting_schedule",
            client_decision="approved",
            schedule_request__isnull=True,
        ).exclude(pk=row.pk)
        for other in others:
            offered = [w for w in (other.proposed_windows or []) if window_key(w) != chosen_key]
            if offered != other.proposed_windows:
                other.proposed_windows = offered
                other.server_version += 1
                other.save(update_fields=["proposed_windows", "server_version", "updated_at"])

    messages.success(request, "Horário solicitado e reservado temporariamente. A Reparos SJC fará a confirmação final.")
    return redirect("corporate:portal")


@login_required
@require_GET
def portal_requests_api(request):
    membership = _membership(request)
    if not membership:
        return JsonResponse({"detail": "forbidden"}, status=403)
    rows = ServiceRequest.objects.filter(organization=membership.organization).select_related("organization")[:100]
    return JsonResponse({"requests": [contract_for(row) for row in rows], "serverTime": timezone.now().isoformat()})
