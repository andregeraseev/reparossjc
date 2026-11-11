from django.db import models


class BackupAccount(models.Model):
    name = models.SlugField(max_length=64, unique=True)
    token_sha256 = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True)


class BackupVersion(models.Model):
    account = models.ForeignKey(BackupAccount, on_delete=models.PROTECT)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    ciphertext = models.BinaryField()
    counts = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "sha256"], name="rsjc_backup_account_digest"),
        ]
        indexes = [models.Index(fields=["account", "-id"], name="rsjc_backup_account_latest")]
