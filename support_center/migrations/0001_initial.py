# Generated for Reparos SJC Support R1.
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="SupportAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("account_key_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("workspace_id", models.CharField(blank=True, db_index=True, default="", max_length=100)),
                ("support_code", models.CharField(db_index=True, max_length=20, unique=True)),
                ("display_name", models.CharField(blank=True, default="", max_length=160)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-last_seen_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="SupportDevice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("installation_id", models.CharField(max_length=120)),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("platform", models.CharField(blank=True, default="android", max_length=32)),
                ("manufacturer", models.CharField(blank=True, default="", max_length=80)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("android_release", models.CharField(blank=True, default="", max_length=40)),
                ("android_sdk", models.PositiveIntegerField(default=0)),
                ("app_version", models.CharField(blank=True, default="", max_length=40)),
                ("app_version_code", models.PositiveBigIntegerField(default=0)),
                ("continuous_sharing", models.BooleanField(default=False)),
                ("privacy_version", models.CharField(blank=True, default="support-r1", max_length=40)),
                ("consent_updated_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to="support_center.supportaccount")),
            ],
            options={"ordering": ["-last_seen_at"]},
        ),
        migrations.CreateModel(
            name="SupportSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="snapshots", to="support_center.supportaccount")),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="snapshots", to="support_center.supportdevice")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SupportEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(max_length=120)),
                ("occurred_at", models.DateTimeField()),
                ("action", models.CharField(max_length=100)),
                ("entity", models.CharField(blank=True, default="system", max_length=80)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warn", "Aviso"), ("error", "Erro")], default="info", max_length=12)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("app_version", models.CharField(blank=True, default="", max_length=40)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="support_center.supportaccount")),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="support_center.supportdevice")),
            ],
            options={"ordering": ["-occurred_at", "-id"]},
        ),
        migrations.CreateModel(
            name="SupportCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("note", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("open", "Aberto"), ("investigating", "Investigando"), ("resolved", "Resolvido")], default="open", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cases", to="support_center.supportaccount")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_cases_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="SupportAccessLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=60)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="access_logs", to="support_center.supportaccount")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_access_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="supportdevice", constraint=models.UniqueConstraint(fields=("account", "installation_id"), name="uniq_support_account_installation")),
        migrations.AddConstraint(model_name="supportevent", constraint=models.UniqueConstraint(fields=("device", "event_id"), name="uniq_support_device_event")),
        migrations.AddIndex(model_name="supportdevice", index=models.Index(fields=["account", "last_seen_at"], name="support_cen_account_b9a75e_idx")),
        migrations.AddIndex(model_name="supportsnapshot", index=models.Index(fields=["device", "-created_at"], name="support_cen_device__5a773b_idx")),
        migrations.AddIndex(model_name="supportsnapshot", index=models.Index(fields=["account", "-created_at"], name="support_cen_account_962578_idx")),
        migrations.AddIndex(model_name="supportevent", index=models.Index(fields=["account", "-occurred_at"], name="support_cen_account_1ecf8a_idx")),
        migrations.AddIndex(model_name="supportevent", index=models.Index(fields=["device", "-occurred_at"], name="support_cen_device__412473_idx")),
        migrations.AddIndex(model_name="supportevent", index=models.Index(fields=["action", "-occurred_at"], name="support_cen_action_f7e527_idx")),
        migrations.AddIndex(model_name="supportaccesslog", index=models.Index(fields=["account", "-created_at"], name="support_cen_account_ebaf43_idx")),
    ]
