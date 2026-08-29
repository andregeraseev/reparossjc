from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("corporate", "0003_portal_channels_and_private_images"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalChannelMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("manager", "Gestor"), ("requester", "Solicitante"), ("viewer", "Consulta")], default="requester", max_length=24)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("portal_channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="corporate.portalchannel")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="corporate_portal_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["portal_channel__sort_order", "portal_channel__display_name", "user__username"]},
        ),
        migrations.CreateModel(
            name="PortalPerson",
            fields=[
                ("id", models.CharField(editable=False, max_length=80, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("role_label", models.CharField(blank=True, default="Manutenção", max_length=120)),
                ("phone", models.CharField(blank=True, default="", max_length=40)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("notes", models.CharField(blank=True, default="", max_length=300)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("portal_channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="people", to="corporate.portalchannel")),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.AddConstraint(
            model_name="portalchannelmembership",
            constraint=models.UniqueConstraint(fields=("user", "portal_channel"), name="uniq_portal_channel_membership"),
        ),
        migrations.AddIndex(
            model_name="portalchannelmembership",
            index=models.Index(fields=["user", "active"], name="corp_pcm_user_active_idx"),
        ),
        migrations.AddIndex(
            model_name="portalchannelmembership",
            index=models.Index(fields=["portal_channel", "active"], name="corp_pcm_channel_active_idx"),
        ),
        migrations.AddIndex(
            model_name="portalperson",
            index=models.Index(fields=["portal_channel", "active", "sort_order"], name="corp_person_channel_idx"),
        ),
    ]
