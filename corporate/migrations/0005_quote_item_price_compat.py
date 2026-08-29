from django.db import migrations


def add_quote_item_price_fallback(apps, schema_editor):
    ServiceRequest = apps.get_model("corporate", "ServiceRequest")
    for row in ServiceRequest.objects.exclude(quote__isnull=True).iterator():
        quote = row.quote
        if not isinstance(quote, dict):
            continue
        items = quote.get("items")
        if not isinstance(items, list):
            continue

        changed = False
        normalized = []
        for item in items:
            if not isinstance(item, dict) or "price" in item:
                normalized.append(item)
                continue
            clone = dict(item)
            clone["price"] = clone.get("total")
            normalized.append(clone)
            changed = True

        if changed:
            quote = dict(quote)
            quote["items"] = normalized
            ServiceRequest.objects.filter(pk=row.pk).update(quote=quote)


class Migration(migrations.Migration):
    dependencies = [
        ("corporate", "0004_v1830_portal_access_people"),
    ]

    operations = [
        migrations.RunPython(add_quote_item_price_fallback, migrations.RunPython.noop),
    ]
