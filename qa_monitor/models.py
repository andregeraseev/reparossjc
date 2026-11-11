from django.db import models


class Tester(models.Model):
    code = models.SlugField(max_length=48, unique=True)
    token_hash = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True)


class Session(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    tester = models.ForeignKey(Tester, on_delete=models.CASCADE)
    received_at = models.DateTimeField(auto_now_add=True)
    digest = models.CharField(max_length=64)
    payload = models.JSONField()
