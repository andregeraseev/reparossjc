from django.contrib import admin

from .models import SupportAccessLog, SupportAccount, SupportCase, SupportDevice, SupportEvent, SupportSnapshot


@admin.register(SupportAccount)
class SupportAccountAdmin(admin.ModelAdmin):
    list_display = ("support_code", "display_name", "workspace_id", "active", "last_seen_at")
    search_fields = ("support_code", "account_key", "workspace_id", "display_name")
    list_filter = ("active",)
    readonly_fields = ("account_key", "support_code")


@admin.register(SupportDevice)
class SupportDeviceAdmin(admin.ModelAdmin):
    list_display = ("account", "manufacturer", "model", "app_version", "android_release", "continuous_sharing", "active", "last_seen_at")
    search_fields = ("account__support_code", "installation_id", "manufacturer", "model")
    list_filter = ("active", "platform", "continuous_sharing")
    readonly_fields = ("token_hash", "installation_id", "consent_updated_at")


@admin.register(SupportEvent)
class SupportEventAdmin(admin.ModelAdmin):
    list_display = ("account", "device", "action", "entity", "severity", "occurred_at", "received_at")
    search_fields = ("account__support_code", "action", "entity", "event_id")
    list_filter = ("severity", "entity")
    readonly_fields = ("detail",)


@admin.register(SupportSnapshot)
class SupportSnapshotAdmin(admin.ModelAdmin):
    list_display = ("account", "device", "created_at")
    search_fields = ("account__support_code", "device__installation_id")
    readonly_fields = ("data",)


@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display = ("account", "title", "status", "created_by", "updated_at")
    search_fields = ("account__support_code", "title", "note")
    list_filter = ("status",)


@admin.register(SupportAccessLog)
class SupportAccessLogAdmin(admin.ModelAdmin):
    list_display = ("account", "user", "action", "created_at")
    search_fields = ("account__support_code", "user__username", "action")
    readonly_fields = ("account", "user", "action", "detail", "created_at")
