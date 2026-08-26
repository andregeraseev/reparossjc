from django.contrib import admin
from .models import AvailabilitySnapshot, Organization, PartnerMembership, ServiceRequest


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("display_name", "slug", "active", "demo", "updated_at")
    search_fields = ("name", "display_name", "slug")


@admin.register(PartnerMembership)
class PartnerMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "active")
    list_filter = ("organization", "role", "active")


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("external_request_id", "organization", "status", "priority", "server_version", "updated_at")
    list_filter = ("organization", "status", "priority")
    search_fields = ("external_request_id", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AvailabilitySnapshot)
class AvailabilitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("workspace_id", "version", "updated_at")
