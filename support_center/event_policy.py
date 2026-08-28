"""Strict vocabulary for Support telemetry event labels.

Event action/entity values are metadata, not free text. Unknown labels are normalized
without preserving the submitted value so names or other private text cannot be smuggled
through fields that are shown in the Support Center timeline.
"""

_ALLOWED_ACTIONS = frozenset({
    "js_error",
    "promise_rejection",
    "support_registered",
    "support_bootstrap_error",
    "support_continuous_changed",
    "support_diagnostic_error",
    "support_diagnostic_sent",
    "corporate_sync",
    "corporate_quote_send",
    "corporate_availability_send",
    "corporate_schedule_confirm",
    "backup_save",
    "backup_restore",
    "commercial_identity_update",
    "data_export",
    "deletion_request_simulated",
    "migration_v15",
    "self_test",
    "server_lab_sync",
    "sync_simulated",
    "changed",
    "delete",
    "updated",
    "created",
    "brand_update",
    "unknown_event",
})

_ALLOWED_ENTITIES = frozenset({
    "system",
    "support",
    "corporate",
    "quote",
    "schedule",
    "backup",
    "workspace",
    "privacy",
    "clients",
    "inventory",
    "jobs",
    "quotes",
    "settings",
    "sync",
})


def normalize_event_action(value):
    raw = str(value or "").strip()
    return raw if raw in _ALLOWED_ACTIONS else "unknown_event"


def normalize_event_entity(value):
    raw = str(value or "system").strip()
    return raw if raw in _ALLOWED_ENTITIES else "system"
