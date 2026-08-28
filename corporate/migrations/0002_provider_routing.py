import hashlib

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def seed_existing_provider_routes(apps, schema_editor):
    Organization = apps.get_model("corporate", "Organization")
    OrganizationProvider = apps.get_model("corporate", "OrganizationProvider")
    ServiceProvider = apps.get_model("corporate", "ServiceProvider")
    ServiceRequest = apps.get_model("corporate", "ServiceRequest")

    default_workspace = (getattr(settings, "CORPORATE_DEFAULT_WORKSPACE_ID", "") or "").strip()
    if default_workspace:
        canonical, _ = ServiceProvider.objects.get_or_create(
            workspace_id=default_workspace,
            defaults={
                "id": "provider_reparos_sjc",
                "slug": "reparos-sjc",
                "name": "Reparos SJC",
                "display_name": "Reparos SJC",
                "active": True,
            },
        )
        for organization in Organization.objects.all():
            OrganizationProvider.objects.get_or_create(
                organization=organization,
                provider=canonical,
                defaults={"active": True, "is_default": True},
            )

    for row in ServiceRequest.objects.select_related("organization").all():
        workspace_id = (row.workspace_id or default_workspace).strip()
        if not workspace_id:
            continue
        provider = ServiceProvider.objects.filter(workspace_id=workspace_id).first()
        if provider is None:
            suffix = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()[:12]
            provider = ServiceProvider.objects.create(
                id=f"provider_legacy_{suffix}",
                slug=f"legacy-{suffix}",
                name=f"Prestador legado {suffix}",
                display_name=f"Prestador legado {suffix}",
                workspace_id=workspace_id,
                active=True,
            )
        OrganizationProvider.objects.get_or_create(
            organization=row.organization,
            provider=provider,
            defaults={"active": True, "is_default": not row.organization.provider_links.filter(is_default=True).exists()},
        )
        row.provider_id = provider.id
        row.workspace_id = workspace_id
        row.save(update_fields=["provider", "workspace_id"])


class Migration(migrations.Migration):
    dependencies = [("corporate", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ServiceProvider",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("display_name", models.CharField(max_length=160)),
                ("workspace_id", models.CharField(db_index=True, max_length=80, unique=True)),
                ("operator_token_hash", models.CharField(blank=True, default="", editable=False, max_length=64)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["display_name"]},
        ),
        migrations.CreateModel(
            name="OrganizationProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="provider_links", to="corporate.organization")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="organization_links", to="corporate.serviceprovider")),
            ],
            options={"ordering": ["sort_order", "provider__display_name"]},
        ),
        migrations.AddConstraint(
            model_name="organizationprovider",
            constraint=models.UniqueConstraint(fields=("organization", "provider"), name="uniq_org_provider"),
        ),
        migrations.AddConstraint(
            model_name="organizationprovider",
            constraint=models.UniqueConstraint(condition=Q(active=True, is_default=True), fields=("organization",), name="uniq_active_default_provider_per_org"),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="provider",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="service_requests", to="corporate.serviceprovider"),
        ),
        migrations.AddIndex(
            model_name="servicerequest",
            index=models.Index(fields=["provider", "updated_at"], name="corporate_s_provide_c402ad_idx"),
        ),
        migrations.RunPython(seed_existing_provider_routes, migrations.RunPython.noop),
    ]
