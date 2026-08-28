from django.contrib import admin

from .models import SupportAccount, SupportCase, SupportDevice, SupportEvent, SupportSnapshot


@admin.register(SupportAccount)
class SupportAccountAdmin(admin.ModelAdmin):
    list_display = ("support_code", "display_name", "workspace_id", "active", "last_seen_at")
    search_fields = ("support_code", "workspace_id", "display_name")
    list_filter = ("active",)


@admin.register(SupportDevice)
class SupportDeviceAdmin(admin.ModelAdmin):
    list_display = ("account", "manufacturer", "model", "app_version", "android_release", "active", "last_seen_at")
    search_fields = ("account__support_code", "installation_id", "manufacturer", "model")
    list_filter = ("active", "platform")
    readonly_fields = ("token_hash",)


@admin.register(SupportEvent)
class SupportEventAdmin(admin.ModelAdmin):
    list_display = ("account", "device", "action", "entity", "severity", "occurred_at")
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
