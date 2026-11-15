import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Tester",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=48, unique=True)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("enabled", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="Session",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("digest", models.CharField(max_length=64)),
                ("payload", models.JSONField()),
                ("tester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="qa_monitor.tester")),
            ],
        ),
    ]
