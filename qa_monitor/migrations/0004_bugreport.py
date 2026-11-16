import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("qa_monitor", "0003_staffaccount_staffsession")]
    operations = [
        migrations.CreateModel(
            name="BugReport",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("received_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("digest", models.CharField(max_length=64)),
                ("payload", models.JSONField()),
                ("screenshot", models.BinaryField(default=bytes)),
                ("tester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="qa_monitor.tester")),
            ],
        ),
    ]
