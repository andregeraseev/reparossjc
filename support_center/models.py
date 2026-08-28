import uuid

from django.conf import settings
from django.db import models


class SupportAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    workspace_id = models.CharField(max_length=100, blank=True, default="", db_index=True)
    support_code = models.CharField(max_length=20, unique=True, db_index=True)
    display_name = models.CharField(max_length=160, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]

    def __str__(self):
        return f"{self.support_code} • {self.display_name or self.workspace_id or 'conta de suporte'}"


class SupportDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(SupportAccount, on_delete=models.CASCADE, related_name="devices")
    installation_id = models.CharField(max_length=120)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    platform = models.CharField(max_length=32, blank=True, default="android")
    manufacturer = models.CharField(max_length=80, blank=True, default="")
    model = models.CharField(max_length=120, blank=True, default="")
    android_release = models.CharField(max_length=40, blank=True, default="")
    android_sdk = models.PositiveIntegerField(default=0)
    app_version = models.CharField(max_length=40, blank=True, default="")
    app_version_code = models.PositiveBigIntegerField(default=0)
    continuous_sharing = models.BooleanField(default=False)
    privacy_version = models.CharField(max_length=40, blank=True, default="support-r1")
    consent_updated_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "installation_id"], name="uniq_support_account_installation")
        ]
        indexes = [models.Index(fields=["account", "last_seen_at"])]
        ordering = ["-last_seen_at"]

    def __str__(self):
        label = " ".join(x for x in (self.manufacturer, self.model) if x).strip() or self.installation_id
        return f"{self.account.support_code} • {label}"


class SupportEvent(models.Model):
    SEVERITY_CHOICES = (("info", "Info"), ("warn", "Aviso"), ("error", "Erro"))

    account = models.ForeignKey(SupportAccount, on_delete=models.CASCADE, related_name="events")
    device = models.ForeignKey(SupportDevice, on_delete=models.CASCADE, related_name="events")
    event_id = models.CharField(max_length=120)
    occurred_at = models.DateTimeField()
    action = models.CharField(max_length=100)
    entity = models.CharField(max_length=80, blank=True, default="system")
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default="info")
    detail = models.JSONField(default=dict, blank=True)
    app_version = models.CharField(max_length=40, blank=True, default="")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "event_id"], name="uniq_support_device_event")]
        indexes = [
            models.Index(fields=["account", "-occurred_at"]),
            models.Index(fields=["device", "-occurred_at"]),
            models.Index(fields=["action", "-occurred_at"]),
        ]
        ordering = ["-occurred_at", "-id"]

    def __str__(self):
        return f"{self.account.support_code} • {self.action}"


class SupportSnapshot(models.Model):
    account = models.ForeignKey(SupportAccount, on_delete=models.CASCADE, related_name="snapshots")
    device = models.ForeignKey(SupportDevice, on_delete=models.CASCADE, related_name="snapshots")
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["device", "-created_at"]), models.Index(fields=["account", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account.support_code} • snapshot {self.created_at:%Y-%m-%d %H:%M}"


class SupportCase(models.Model):
    STATUS_CHOICES = (("open", "Aberto"), ("investigating", "Investigando"), ("resolved", "Resolvido"))

    account = models.ForeignKey(SupportAccount, on_delete=models.CASCADE, related_name="cases")
    title = models.CharField(max_length=180)
    note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_cases_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.account.support_code} • {self.title}"


class SupportAccessLog(models.Model):
    account = models.ForeignKey(SupportAccount, on_delete=models.CASCADE, related_name="access_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_access_logs")
    action = models.CharField(max_length=60)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["account", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account.support_code} • {self.user} • {self.action}"
