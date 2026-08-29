"""Compatibility dispatcher for Corporate portal v18.30.

Users explicitly enrolled in PortalChannelMembership get the strict v18.30
channel-scoped experience. Existing organization-only users keep the proven R1
flow unchanged until they are migrated deliberately.
"""

from . import portal_v1830, views as legacy_views
from .models import PortalChannelMembership


def _uses_v1830(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and PortalChannelMembership.objects.filter(
            user=user,
            active=True,
            portal_channel__active=True,
            portal_channel__organization__active=True,
        ).exists()
    )


def portal_home(request, organization_slug=None, channel_slug=None):
    if _uses_v1830(request.user):
        return portal_v1830.portal_home(request, organization_slug, channel_slug)
    return legacy_views.portal_home(request, organization_slug, channel_slug)


def portal_create(request):
    if _uses_v1830(request.user):
        return portal_v1830.portal_create(request)
    return legacy_views.portal_create(request)


def portal_approve(request, request_id):
    if _uses_v1830(request.user):
        return portal_v1830.portal_approve(request, request_id)
    return legacy_views.portal_approve(request, request_id)


def portal_schedule(request, request_id):
    if _uses_v1830(request.user):
        return portal_v1830.portal_schedule(request, request_id)
    return legacy_views.portal_schedule(request, request_id)


def portal_attachment(request, attachment_id):
    if _uses_v1830(request.user):
        return portal_v1830.portal_attachment(request, attachment_id)
    return legacy_views.portal_attachment(request, attachment_id)


def portal_requests_api(request):
    if _uses_v1830(request.user):
        return portal_v1830.portal_requests_api(request)
    return legacy_views.portal_requests_api(request)


# People management only exists in the scoped v18.30 model. The implementation
# performs its own role/channel authorization as a second layer.
portal_person_save = portal_v1830.portal_person_save
portal_person_toggle = portal_v1830.portal_person_toggle
