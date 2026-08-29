from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import (
    AvailabilitySnapshot,
    OrganizationProvider,
    PartnerMembership,
    PortalChannel,
    PortalChannelMembership,
    PortalPerson,
    ServiceRequest,
    ServiceRequestAttachment,
)
from .services import contract_for, new_request_id, normalize_public_windows, window_is_future, window_key
from .uploads import UploadValidationError, create_attachments, validate_images


def _scopes(user):
    return PortalChannelMembership.objects.select_related(
        "portal_channel", "portal_channel__organization", "portal_channel__default_provider"
    ).filter(
        user=user,
        active=True,
        portal_channel__active=True,
        portal_channel__organization__active=True,
    )


def _legacy_memberships(user):
    return PartnerMembership.objects.select_related("organization").filter(
        user=user,
        active=True,
        organization__active=True,
    )


def _organization_for(user, organization_slug=None):
    scoped = _scopes(user)
    if scoped.exists():
        if organization_slug:
            scoped = scoped.filter(portal_channel__organization__slug=organization_slug)
        row = scoped.first()
        return row.portal_channel.organization if row else None
    legacy = _legacy_memberships(user)
    if organization_slug:
        legacy = legacy.filter(organization__slug=organization_slug)
    row = legacy.first()
    return row.organization if row else None


def _channels_for(user, organization):
    scoped = _scopes(user).filter(portal_channel__organization=organization)
    if scoped.exists():
        ids = list(scoped.values_list("portal_channel_id", flat=True))
        return list(
            PortalChannel.objects.filter(id__in=ids, active=True)
            .select_related("organization", "default_provider")
            .order_by("sort_order", "display_name")
        )
    if _legacy_memberships(user).filter(organization=organization).exists():
        return list(
            PortalChannel.objects.filter(organization=organization, active=True)
            .select_related("organization", "default_provider")
            .order_by("sort_order", "display_name")
        )
    return []


def _role_for(user, channel):
    scope = _scopes(user).filter(portal_channel=channel).first()
    if scope:
        return scope.role
    legacy = _legacy_memberships(user).filter(organization=channel.organization).first()
    return legacy.role if legacy else ""


def _can_submit(role):
    return role in {"manager", "requester"}


def _can_manage_people(role):
    return role == "manager"


def _channel_for(user, organization, channel_slug=None, channel_id=None):
    channels = _channels_for(user, organization)
    if channel_id:
        return next((row for row in channels if str(row.id) == str(channel_id)), None), channels
    if channel_slug:
        return next((row for row in channels if row.slug == channel_slug), None), channels
    return (channels[0] if channels else None), channels


def _access_for_request(user, request_id):
    row = ServiceRequest.objects.select_related("organization", "provider", "portal_channel").filter(pk=request_id).first()
    if not row:
        raise Http404("Chamado não encontrado")
    scoped = _scopes(user)
    if scoped.exists():
        if not row.portal_channel_id or not scoped.filter(portal_channel_id=row.portal_channel_id).exists():
            return None, row
        return _role_for(user, row.portal_channel), row
    legacy = _legacy_memberships(user).filter(organization=row.organization).first()
    return (legacy.role if legacy else None), row


def _provider_links(organization):
    return list(
        OrganizationProvider.objects.filter(
            organization=organization,
            active=True,
            provider__active=True,
        ).select_related("provider")
    )


def _redirect(row=None, channel=None):
    channel = channel or getattr(row, "portal_channel", None)
    organization = getattr(row, "organization", None) or getattr(channel, "organization", None)
    if channel and organization:
        return redirect(reverse("corporate:portal_channel", args=[organization.slug, channel.slug]))
    return redirect("corporate:portal")


def _attachment_response(attachment):
    try:
        attachment.file.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("Imagem não encontrada")
    suffix = attachment.file.name.rsplit(".", 1)[-1].lower()
    filename = f"{attachment.display_name}.{suffix}"
    response = FileResponse(attachment.file, content_type=attachment.content_type, as_attachment=False, filename=filename)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _reserved_window_keys(workspace_id, exclude_request_id=None):
    qs = ServiceRequest.objects.filter(
        workspace_id=workspace_id,
        status__in=("schedule_requested", "scheduled", "in_service"),
        schedule_request__isnull=False,
    )
    if exclude_request_id:
        qs = qs.exclude(pk=exclude_request_id)
    return {window_key(row.schedule_request) for row in qs.only("schedule_request") if row.schedule_request}


@login_required
def portal_home(request, organization_slug=None, channel_slug=None):
    organization = _organization_for(request.user, organization_slug)
    if not organization:
        return render(request, "corporate/no_access.html", status=403)
    channel, channels = _channel_for(request.user, organization, channel_slug=channel_slug)
    if channel_slug and channel is None:
        raise Http404("Portal não encontrado ou não autorizado")
    if channel is None:
        return render(request, "corporate/no_access.html", {"detail": "Nenhum portal ativo autorizado."}, status=403)

    role = _role_for(request.user, channel)
    rows = (
        ServiceRequest.objects.filter(organization=organization, portal_channel=channel)
        .select_related("organization", "provider", "portal_channel")
        .prefetch_related("image_attachments")[:100]
    )
    provider_links = _provider_links(organization)
    selected_provider_id = channel.default_provider_id if channel.default_provider_id and any(
        link.provider_id == channel.default_provider_id for link in provider_links
    ) else next((link.provider_id for link in provider_links if link.is_default), "")
    if not selected_provider_id and len(provider_links) == 1:
        selected_provider_id = provider_links[0].provider_id

    people = list(PortalPerson.objects.filter(portal_channel=channel).order_by("sort_order", "name"))
    active_people = [person for person in people if person.active]
    return render(
        request,
        "corporate/portal_v1830.html",
        {
            "organization": organization,
            "portal_channel": channel,
            "portal_channels": channels,
            "requests": rows,
            "provider_links": provider_links,
            "selected_provider_id": selected_provider_id,
            "portal_role": role,
            "can_submit": _can_submit(role),
            "can_manage_people": _can_manage_people(role),
            "portal_people": people,
            "active_portal_people": active_people,
        },
    )


@login_required
@require_POST
def portal_create(request):
    organization = _organization_for(request.user, request.POST.get("organization_slug", "").strip() or None)
    if not organization:
        return JsonResponse({"detail": "forbidden"}, status=403)
    channel, _ = _channel_for(
        request.user,
        organization,
        channel_id=request.POST.get("portal_channel_id", "").strip() or None,
    )
    if channel is None:
        return JsonResponse({"detail": "portal forbidden"}, status=403)
    role = _role_for(request.user, channel)
    if not _can_submit(role):
        return JsonResponse({"detail": "read-only portal access"}, status=403)

    provider_links = _provider_links(organization)
    provider_id = request.POST.get("provider_id", "").strip()
    provider_link = next((link for link in provider_links if link.provider_id == provider_id), None)
    if provider_link is None and not provider_id:
        provider_link = next((link for link in provider_links if link.provider_id == channel.default_provider_id), None)
        provider_link = provider_link or next((link for link in provider_links if link.is_default), None)
        if provider_link is None and len(provider_links) == 1:
            provider_link = provider_links[0]
    if provider_link is None:
        messages.error(request, "Selecione um prestador autorizado para enviar o chamado.")
        return _redirect(channel=channel)

    external = request.POST.get("external_request_id", "").strip()
    if not external:
        external = f"{organization.slug.upper()[:8]}-{channel.slug.upper()[:8]}-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}"
    if ServiceRequest.objects.filter(organization=organization, external_request_id=external).exists():
        messages.error(request, "Já existe um chamado com esse número.")
        return _redirect(channel=channel)

    try:
        images = validate_images(request.FILES.getlist("images"))
    except UploadValidationError as exc:
        messages.error(request, str(exc))
        return _redirect(channel=channel)

    selected_person = None
    person_id = request.POST.get("portal_person_id", "").strip()
    if person_id:
        selected_person = PortalPerson.objects.filter(pk=person_id, portal_channel=channel, active=True).first()
        if selected_person is None:
            messages.error(request, "A pessoa selecionada não está mais disponível neste portal.")
            return _redirect(channel=channel)

    requester_name = request.POST.get("requester_name", "").strip()
    requester_phone = request.POST.get("requester_phone", "").strip()
    requester_email = request.user.email or ""
    requester_role = ""
    if selected_person:
        requester_name = selected_person.name
        requester_phone = selected_person.phone
        requester_email = selected_person.email
        requester_role = selected_person.role_label
    if not requester_name:
        requester_name = request.user.get_full_name() or request.user.username

    with transaction.atomic():
        row = ServiceRequest.objects.create(
            id=new_request_id(),
            external_request_id=external[:120],
            organization=organization,
            portal_channel=channel,
            provider=provider_link.provider,
            workspace_id=provider_link.provider.workspace_id,
            location={
                "label": request.POST.get("location", "").strip(),
                "address": request.POST.get("address", "").strip(),
            },
            requester={
                "name": requester_name,
                "phone": requester_phone,
                "email": requester_email,
                "personId": selected_person.id if selected_person else "",
                "role": requester_role,
            },
            category=request.POST.get("category", "").strip() or channel.default_category or "Manutenção",
            priority=request.POST.get("priority", "").strip() or "Normal",
            description=request.POST.get("description", "").strip(),
            status="new",
        )
        create_attachments(row, images, uploaded_by=request.user)

    image_text = f" com {len(images)} foto(s)" if images else ""
    messages.success(
        request,
        f"Chamado {row.external_request_id}{image_text} enviado para {provider_link.provider.display_name}.",
    )
    return _redirect(row=row)


@login_required
@require_POST
def portal_person_save(request):
    organization = _organization_for(request.user, request.POST.get("organization_slug", "").strip() or None)
    if not organization:
        return JsonResponse({"detail": "forbidden"}, status=403)
    channel, _ = _channel_for(request.user, organization, channel_id=request.POST.get("portal_channel_id", "").strip())
    if channel is None or not _can_manage_people(_role_for(request.user, channel)):
        return JsonResponse({"detail": "manager access required"}, status=403)

    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Informe o nome da pessoa.")
        return _redirect(channel=channel)
    person_id = request.POST.get("person_id", "").strip()
    person = PortalPerson.objects.filter(pk=person_id, portal_channel=channel).first() if person_id else PortalPerson(portal_channel=channel)
    if person is None:
        messages.error(request, "Pessoa não encontrada neste portal.")
        return _redirect(channel=channel)
    person.name = name[:160]
    person.role_label = request.POST.get("role_label", "").strip()[:120] or "Manutenção"
    person.phone = request.POST.get("phone", "").strip()[:40]
    person.email = request.POST.get("email", "").strip()[:254]
    person.notes = request.POST.get("notes", "").strip()[:300]
    person.active = request.POST.get("active", "1") != "0"
    person.save()
    messages.success(request, f"Cadastro de {person.name} salvo no portal {channel.display_name}.")
    return _redirect(channel=channel)


@login_required
@require_POST
def portal_person_toggle(request, person_id):
    person = get_object_or_404(PortalPerson.objects.select_related("portal_channel__organization"), pk=person_id)
    channel = person.portal_channel
    allowed, _ = _channel_for(request.user, channel.organization, channel_id=channel.id)
    if allowed is None or not _can_manage_people(_role_for(request.user, channel)):
        return JsonResponse({"detail": "manager access required"}, status=403)
    person.active = not person.active
    person.save(update_fields=["active", "updated_at"])
    state = "ativado" if person.active else "desativado"
    messages.success(request, f"{person.name} {state} neste portal.")
    return _redirect(channel=channel)


@login_required
@require_POST
def portal_approve(request, request_id):
    role, row = _access_for_request(request.user, request_id)
    if not role:
        return JsonResponse({"detail": "forbidden"}, status=403)
    if not _can_submit(role):
        return JsonResponse({"detail": "read-only portal access"}, status=403)
    with transaction.atomic():
        row = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id)
        if not row.quote:
            return HttpResponseBadRequest("Orçamento ainda não disponível")
        if row.status in {"scheduled", "in_service", "completed", "cancelled", "rejected"}:
            messages.error(request, "Esse chamado não pode mais ser aprovado nesta etapa.")
            return _redirect(row=row)
        row.client_decision = "approved"
        row.status = "quote_approved"
        row.proposed_windows = []
        row.server_version += 1
        row.save(update_fields=["client_decision", "status", "proposed_windows", "server_version", "updated_at"])
    provider_name = row.provider.display_name if row.provider_id else "o prestador"
    messages.success(request, f"Orçamento aprovado. Aguardando {provider_name} oferecer horários.")
    return _redirect(row=row)


@login_required
@require_POST
def portal_schedule(request, request_id):
    role, row = _access_for_request(request.user, request_id)
    if not role:
        return JsonResponse({"detail": "forbidden"}, status=403)
    if not _can_submit(role):
        return JsonResponse({"detail": "read-only portal access"}, status=403)
    source_id = request.POST.get("source_id", "").strip()

    with transaction.atomic():
        row = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id)
        if row.status != "waiting_schedule" or row.client_decision != "approved" or row.schedule_request:
            messages.error(request, "Esse chamado não está aguardando escolha de horário.")
            return _redirect(row=row)
        chosen = next((w for w in (row.proposed_windows or []) if str(w.get("sourceId") or "") == source_id), None)
        if not chosen or not window_is_future(chosen):
            messages.error(request, "Esse horário não está mais disponível. Escolha outra opção.")
            return _redirect(row=row)

        workspace_id = row.workspace_id or getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", "")
        snap = AvailabilitySnapshot.objects.select_for_update().filter(pk=workspace_id).first()
        if snap is None or window_key(chosen) not in {
            window_key(w) for w in normalize_public_windows(snap.windows, limit=100, require_future=True)
        }:
            messages.error(request, "Esse horário acabou de ficar indisponível. Escolha outra opção.")
            return _redirect(row=row)
        if window_key(chosen) in _reserved_window_keys(row.workspace_id, exclude_request_id=row.pk):
            messages.error(request, "Esse horário acabou de ser reservado por outro atendimento. Escolha outra opção.")
            return _redirect(row=row)

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

        chosen_key = window_key(chosen)
        next_snapshot = [
            w for w in normalize_public_windows(snap.windows, limit=100, require_future=True)
            if window_key(w) != chosen_key
        ]
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

    provider_name = row.provider.display_name if row.provider_id else "O prestador"
    messages.success(request, f"Horário solicitado e reservado. {provider_name} fará a confirmação final.")
    return _redirect(row=row)


@login_required
@require_GET
def portal_attachment(request, attachment_id):
    attachment = get_object_or_404(
        ServiceRequestAttachment.objects.select_related("service_request__organization", "service_request__portal_channel"),
        pk=attachment_id,
    )
    role, row = _access_for_request(request.user, attachment.service_request_id)
    if not role or row.id != attachment.service_request_id:
        raise Http404("Imagem não encontrada")
    return _attachment_response(attachment)


@login_required
@require_GET
def portal_requests_api(request):
    organization = _organization_for(request.user, request.GET.get("organization", "").strip() or None)
    if not organization:
        return JsonResponse({"detail": "forbidden"}, status=403)
    channel, channels = _channel_for(
        request.user,
        organization,
        channel_id=request.GET.get("portal_channel_id", "").strip() or None,
    )
    allowed_ids = [row.id for row in channels]
    rows = ServiceRequest.objects.filter(organization=organization, portal_channel_id__in=allowed_ids)
    if channel and request.GET.get("portal_channel_id"):
        rows = rows.filter(portal_channel=channel)
    rows = rows.select_related("organization", "provider", "portal_channel").prefetch_related("image_attachments")[:100]
    return JsonResponse({"requests": [contract_for(row) for row in rows], "serverTime": timezone.now().isoformat()})
