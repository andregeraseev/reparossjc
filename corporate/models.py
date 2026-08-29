from django.conf import settings
from django.db import models
from django.db.models import Q


class Organization(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    display_name = models.CharField(max_length=160)
    demo = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name


class PartnerMembership(models.Model):
    ROLE_CHOICES = (("manager", "Gestor"), ("requester", "Solicitante"), ("viewer", "Consulta"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="corporate_memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=24, choices=ROLE_CHOICES, default="requester")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "organization"], name="uniq_partner_membership")]

    def __str__(self):
        return f"{self.user} @ {self.organization}"


class ServiceProvider(models.Model):
    """A provider app/workspace that can receive Corporate requests."""

    id = models.CharField(max_length=64, primary_key=True)
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    display_name = models.CharField(max_length=160)
    workspace_id = models.CharField(max_length=80, unique=True, db_index=True)
    operator_token_hash = models.CharField(max_length=64, blank=True, default="", editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name


class OrganizationProvider(models.Model):
    """Explicit allow-list of providers an organization may select."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="provider_links")
    provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name="organization_links")
    active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "provider__display_name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "provider"], name="uniq_org_provider"),
            models.UniqueConstraint(
                fields=["organization"],
                condition=Q(active=True, is_default=True),
                name="uniq_active_default_provider_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.organization} → {self.provider}"


class PortalChannel(models.Model):
    """Named intake surface inside an organization (for example Amil Jurídico)."""

    id = models.CharField(max_length=80, primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="portal_channels")
    slug = models.SlugField(max_length=80)
    display_name = models.CharField(max_length=160)
    default_category = models.CharField(max_length=120, blank=True, default="Manutenção")
    instructions = models.CharField(max_length=300, blank=True, default="")
    default_provider = models.ForeignKey(
        ServiceProvider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="default_portal_channels",
    )
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "display_name"]
        constraints = [models.UniqueConstraint(fields=["organization", "slug"], name="uniq_org_portal_slug")]

    def __str__(self):
        return self.display_name


class ServiceRequest(models.Model):
    STATUS_CHOICES = (
        ("new", "Novo"),
        ("reviewing", "Em análise"),
        ("waiting_information", "Aguardando informação"),
        ("quote_sent", "Orçamento enviado"),
        ("quote_approved", "Orçamento aprovado"),
        ("waiting_schedule", "Aguardando agendamento"),
        ("schedule_requested", "Horário solicitado"),
        ("scheduled", "Agendado"),
        ("in_service", "Em atendimento"),
        ("completed", "Concluído"),
        ("rejected", "Recusado"),
        ("cancelled", "Cancelado"),
    )

    id = models.CharField(max_length=80, primary_key=True)
    external_request_id = models.CharField(max_length=120)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="service_requests")
    portal_channel = models.ForeignKey(
        PortalChannel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_requests",
    )
    provider = models.ForeignKey(
        ServiceProvider,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="service_requests",
    )
    workspace_id = models.CharField(max_length=80, blank=True, default="")
    location = models.JSONField(default=dict, blank=True)
    requester = models.JSONField(default=dict, blank=True)
    category = models.CharField(max_length=120, blank=True, default="Reparos")
    priority = models.CharField(max_length=40, blank=True, default="Normal")
    description = models.TextField(blank=True, default="")
    attachments = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default="new")
    client_decision = models.CharField(max_length=40, blank=True, default="")
    provider_local_id = models.CharField(max_length=80, blank=True, default="")
    quote = models.JSONField(null=True, blank=True)
    proposed_windows = models.JSONField(default=list, blank=True)
    schedule_request = models.JSONField(null=True, blank=True)
    appointment = models.JSONField(null=True, blank=True)
    server_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "external_request_id"], name="uniq_org_external_request")]
        indexes = [
            models.Index(fields=["workspace_id", "updated_at"]),
            models.Index(fields=["provider", "updated_at"], name="corporate_s_provide_c402ad_idx"),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.organization.display_name} • {self.external_request_id}"


def corporate_attachment_path(instance, filename):
    suffix = (filename or "image.jpg").rsplit(".", 1)[-1].lower()
    return f"corporate/{instance.service_request.organization_id}/{instance.service_request_id}/{instance.id}.{suffix}"


class ServiceRequestAttachment(models.Model):
    id = models.CharField(max_length=80, primary_key=True)
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="image_attachments")
    file = models.FileField(upload_to=corporate_attachment_path, max_length=300)
    display_name = models.CharField(max_length=120)
    content_type = models.CharField(max_length=80)
    size_bytes = models.PositiveIntegerField()
    checksum_sha256 = models.CharField(max_length=64, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="corporate_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.service_request_id} • {self.display_name}"


class AvailabilitySnapshot(models.Model):
    workspace_id = models.CharField(max_length=80, primary_key=True)
    windows = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.workspace_id


# v18.30 portal operations models live in a small separate module so the
# established Corporate schema above remains readable and backwards compatible.
from .portal_v1830_models import PortalChannelMembership, PortalPerson  # noqa: E402,F401
