from django.conf import settings
from django.db import models


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
        indexes = [models.Index(fields=["workspace_id", "updated_at"]), models.Index(fields=["organization", "status"])]

    def __str__(self):
        return f"{self.organization.display_name} • {self.external_request_id}"


class AvailabilitySnapshot(models.Model):
    workspace_id = models.CharField(max_length=80, primary_key=True)
    windows = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.workspace_id
