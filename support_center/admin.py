from django.contrib import admin

from .models import SupportAccessLog, SupportAccount, SupportCase, SupportDevice, SupportEvent, SupportSnapshot


@admin.register(SupportAccount)
class SupportAccountAdmin(admin.ModelAdmin):
    list_display = ("support_code", "display_name", "workspace_id", "active", "last_seen_at")
    search_fields = ("support_code", "workspace_id", "display_name")
    list_filter = ("active",)
    readonly_fields = ("support_code",)
    exclude = ("account_key_hash",)

    def has_add_permission(self, request):
        return False


@admin.register(SupportDevice)
class SupportDeviceAdmin(admin.ModelAdmin):
    list_display = ("account", "manufacturer", "model", "app_version", "android_release", "continuous_sharing", "active", "last_seen_at")
    search_fields = ("account__support_code", "manufacturer", "model")
    list_filter = ("active", "platform", "continuous_sharing")
    readonly_fields = ("installation_id", "consent_updated_at")
    exclude = ("token_hash",)

    def has_add_permission(self, request):
        return False


@admin.register(SupportEvent)
class SupportEventAdmin(admin.ModelAdmin):
    list_display = ("account", "device", "action", "entity", "severity", "occurred_at", "received_at")
    search_fields = ("account__support_code", "action", "entity", "event_id")
    list_filter = ("severity", "entity")
    readonly_fields = ("account", "device", "event_id", "occurred_at", "action", "entity", "severity", "detail", "app_version", "received_at")

    def has_add_permission(self, request):
        return False


@admin.register(SupportSnapshot)
class SupportSnapshotAdmin(admin.ModelAdmin):
    list_display = ("account", "device", "created_at")
    search_fields = ("account__support_code", "device__model")
    readonly_fields = ("account", "device", "data", "created_at")

    def has_add_permission(self, request):
        return False


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

    def has_add_permission(self, request):
        return False
