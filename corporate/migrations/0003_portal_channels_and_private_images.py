import hashlib

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import corporate.models


def create_default_channels(apps, schema_editor):
    Organization = apps.get_model("corporate", "Organization")
    PortalChannel = apps.get_model("corporate", "PortalChannel")
    for organization in Organization.objects.all():
        provider_link = organization.provider_links.filter(active=True, is_default=True).first()
        if provider_link is None:
            provider_link = organization.provider_links.filter(active=True).first()
        suffix = hashlib.sha256(str(organization.pk).encode("utf-8")).hexdigest()[:22]
        PortalChannel.objects.get_or_create(
            organization=organization,
            slug="geral",
            defaults={
                "id": "PC" + suffix,
                "display_name": f"{organization.display_name} • Chamados"[:160],
                "default_category": "Manutenção",
                "default_provider_id": provider_link.provider_id if provider_link else None,
                "active": True,
            },
        )


def link_existing_requests(apps, schema_editor):
    PortalChannel = apps.get_model("corporate", "PortalChannel")
    ServiceRequest = apps.get_model("corporate", "ServiceRequest")
    for organization_id in ServiceRequest.objects.values_list("organization_id", flat=True).distinct():
        channel = PortalChannel.objects.filter(organization_id=organization_id, slug="geral").first()
        if channel:
            ServiceRequest.objects.filter(organization_id=organization_id, portal_channel__isnull=True).update(portal_channel=channel)


class Migration(migrations.Migration):
    dependencies = [("corporate", "0002_provider_routing")]

    operations = [
        migrations.CreateModel(
            name="PortalChannel",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=80)),
                ("display_name", models.CharField(max_length=160)),
                ("default_category", models.CharField(blank=True, default="Manutenção", max_length=120)),
                ("instructions", models.CharField(blank=True, default="", max_length=300)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("default_provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="default_portal_channels", to="corporate.serviceprovider")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_channels", to="corporate.organization")),
            ],
            options={"ordering": ["sort_order", "display_name"]},
        ),
        migrations.AddConstraint(
            model_name="portalchannel",
            constraint=models.UniqueConstraint(fields=("organization", "slug"), name="uniq_org_portal_slug"),
        ),
        migrations.RunPython(create_default_channels, migrations.RunPython.noop),
        migrations.AddField(
            model_name="servicerequest",
            name="portal_channel",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_requests", to="corporate.portalchannel"),
        ),
        migrations.RunPython(link_existing_requests, migrations.RunPython.noop),
        migrations.CreateModel(
            name="ServiceRequestAttachment",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("file", models.FileField(max_length=300, upload_to=corporate.models.corporate_attachment_path)),
                ("display_name", models.CharField(max_length=120)),
                ("content_type", models.CharField(max_length=80)),
                ("size_bytes", models.PositiveIntegerField()),
                ("checksum_sha256", models.CharField(editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("service_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="image_attachments", to="corporate.servicerequest")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="corporate_attachments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
