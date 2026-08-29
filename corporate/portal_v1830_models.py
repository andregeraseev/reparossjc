from uuid import uuid4

from django.conf import settings
from django.db import models


class PortalChannelMembership(models.Model):
    """Restricts one portal user to one or more intake channels."""

    ROLE_CHOICES = (("manager", "Gestor"), ("requester", "Solicitante"), ("viewer", "Consulta"))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="corporate_portal_memberships",
    )
    portal_channel = models.ForeignKey(
        "corporate.PortalChannel",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=24, choices=ROLE_CHOICES, default="requester")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "corporate"
        ordering = ["portal_channel__sort_order", "portal_channel__display_name", "user__username"]
        constraints = [
            models.UniqueConstraint(fields=["user", "portal_channel"], name="uniq_portal_channel_membership")
        ]
        indexes = [
            models.Index(fields=["user", "active"], name="corp_pcm_user_active_idx"),
            models.Index(fields=["portal_channel", "active"], name="corp_pcm_channel_active_idx"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.portal_channel}"


class PortalPerson(models.Model):
    """A person/contact maintained by a single portal channel.

    Personal details stay in the corporate database and must not be copied to
    support telemetry. A service request may copy a point-in-time snapshot into
    its existing requester JSON payload.
    """

    id = models.CharField(max_length=80, primary_key=True, editable=False)
    portal_channel = models.ForeignKey(
        "corporate.PortalChannel",
        on_delete=models.CASCADE,
        related_name="people",
    )
    name = models.CharField(max_length=160)
    role_label = models.CharField(max_length=120, blank=True, default="Manutenção")
    phone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    notes = models.CharField(max_length=300, blank=True, default="")
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "corporate"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["portal_channel", "active", "sort_order"], name="corp_person_channel_idx")
        ]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = "PP" + uuid4().hex[:22]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.portal_channel} • {self.name}"
