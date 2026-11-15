import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("qa_monitor", "0002_loginwindow")]

    operations = [
        migrations.CreateModel(
            name="StaffAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.SlugField(max_length=48, unique=True)),
                ("password_hash", models.CharField(max_length=128)),
                ("enabled", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="StaffSession",
            fields=[
                ("key_hash", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("staff", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="qa_monitor.staffaccount")),
            ],
        ),
    ]
