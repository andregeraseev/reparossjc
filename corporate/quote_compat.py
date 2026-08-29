"""Compatibility helpers for quote payloads rendered by Corporate portals.

The Android app may send line items with a final ``total`` and no unit ``price``.
Older portal templates resolve ``price`` as the fallback argument even when
``total`` is present, so the key must exist to keep rendering safe.
"""

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import ServiceRequest


def normalize_quote_items(quote):
    if not isinstance(quote, dict):
        return quote
    items = quote.get("items")
    if not isinstance(items, list):
        return quote

    changed = False
    normalized = []
    for item in items:
        if not isinstance(item, dict) or "price" in item:
            normalized.append(item)
            continue
        row = dict(item)
        # ``price`` is only a compatibility fallback for the template. When a
        # line total exists, mirroring it here does not change the displayed
        # amount because ``total`` remains the primary field.
        row["price"] = row.get("total")
        normalized.append(row)
        changed = True

    if not changed:
        return quote
    out = dict(quote)
    out["items"] = normalized
    return out


@receiver(pre_save, sender=ServiceRequest)
def normalize_service_request_quote(sender, instance, **kwargs):
    instance.quote = normalize_quote_items(instance.quote)
