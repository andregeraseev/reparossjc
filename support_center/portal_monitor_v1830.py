from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import SupportAccount
from .services import sanitize_snapshot as sanitize_snapshot_base


PORTAL_OP_KEYS = (
    "total",
    "new",
    "reviewing",
    "quotePending",
    "schedulePending",
    "scheduled",
    "inService",
    "completed",
    "crisTeste",
    "amilJuridico",
    "amilManutencao",
    "amilDistrato",
    "other",
)


def _safe_count(value):
    try:
        value = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return min(1_000_000, max(0, value))


def sanitize_portal_ops(value):
    if not isinstance(value, dict):
        return {}
    return {key: _safe_count(value.get(key)) for key in PORTAL_OP_KEYS if key in value}


def sanitize_snapshot_v1830(data):
    """Extend the existing allow-list with aggregate portal-operation counters only.

    No request ids, portal-person ids, names, phones, addresses, descriptions,
    images, categories or free-text portal labels are accepted here.
    """
    clean = sanitize_snapshot_base(data)
    portal_ops = sanitize_portal_ops(data.get("portalOps") if isinstance(data, dict) else None)
    if portal_ops:
        clean["portalOps"] = portal_ops
    return clean


def _safe_sync(snapshot):
    sync = snapshot.get("sync") if isinstance(snapshot, dict) else {}
    if not isinstance(sync, dict):
        sync = {}
    return {
        "pendingCount": _safe_count(sync.get("pendingCount")),
        "corporateConfigured": bool(sync.get("corporateConfigured")),
        "corporateLastSyncAt": str(sync.get("corporateLastSyncAt") or "")[:80],
        "corporateLastErrorCode": str(sync.get("corporateLastErrorCode") or "")[:80],
    }


@staff_member_required
@never_cache
def portal_ops_feed(request):
    """AI/support-friendly technical feed without Corporate customer content."""
    rows = []
    accounts = SupportAccount.objects.filter(active=True).prefetch_related("devices")[:100]
    for account in accounts:
        for device in account.devices.filter(active=True).order_by("-last_seen_at")[:3]:
            snapshot = device.snapshots.first()
            data = snapshot.data if snapshot else {}
            portal_ops = sanitize_portal_ops((data or {}).get("portalOps"))
            if not portal_ops and not (data or {}).get("sync"):
                continue
            rows.append(
                {
                    "supportCode": account.support_code,
                    "deviceId": str(device.id),
                    "appVersion": str(device.app_version or "")[:40],
                    "appVersionCode": int(device.app_version_code or 0),
                    "lastSeenAt": device.last_seen_at.isoformat() if device.last_seen_at else None,
                    "snapshotAt": snapshot.created_at.isoformat() if snapshot else None,
                    "portalOps": portal_ops,
                    "sync": _safe_sync(data or {}),
                }
            )
    rows.sort(key=lambda item: item.get("lastSeenAt") or "", reverse=True)
    return JsonResponse(
        {
            "schema": "rsjc-support-portal-ops-v1",
            "generatedAt": timezone.now().isoformat(),
            "privacy": "aggregate-technical-only",
            "devices": rows,
        }
    )
