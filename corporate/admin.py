from django.contrib import admin
from .models import (
    AvailabilitySnapshot,
    Organization,
    OrganizationProvider,
    PartnerMembership,
    PortalChannel,
    ServiceProvider,
    ServiceRequest,
    ServiceRequestAttachment,
)


class PortalChannelInline(admin.TabularInline):
    model = PortalChannel
    extra = 0
    fields = ("display_name", "slug", "default_category", "default_provider", "active", "sort_order")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("display_name", "slug", "active", "demo", "updated_at")
    search_fields = ("name", "display_name", "slug")
    inlines = (PortalChannelInline,)


@admin.register(PartnerMembership)
class PartnerMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "active")
    list_filter = ("organization", "role", "active")


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ("display_name", "slug", "workspace_id", "active", "updated_at")
    list_filter = ("active",)
    search_fields = ("name", "display_name", "slug", "workspace_id")
    readonly_fields = ("operator_token_hash", "created_at", "updated_at")


@admin.register(OrganizationProvider)
class OrganizationProviderAdmin(admin.ModelAdmin):
    list_display = ("organization", "provider", "active", "is_default", "sort_order")
    list_filter = ("organization", "provider", "active", "is_default")


@admin.register(PortalChannel)
class PortalChannelAdmin(admin.ModelAdmin):
    list_display = ("display_name", "organization", "slug", "default_category", "default_provider", "active", "sort_order")
    list_filter = ("organization", "active", "default_provider")
    search_fields = ("display_name", "slug", "organization__display_name")


class ServiceRequestAttachmentInline(admin.TabularInline):
    model = ServiceRequestAttachment
    extra = 0
    readonly_fields = ("display_name", "content_type", "size_bytes", "checksum_sha256", "uploaded_by", "created_at")
    fields = readonly_fields
    can_delete = False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("external_request_id", "organization", "portal_channel", "provider", "status", "priority", "server_version", "updated_at")
    list_filter = ("organization", "portal_channel", "provider", "status", "priority")
    search_fields = ("external_request_id", "description")
    readonly_fields = ("created_at", "updated_at")
    inlines = (ServiceRequestAttachmentInline,)


@admin.register(AvailabilitySnapshot)
class AvailabilitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("workspace_id", "version", "updated_at")
