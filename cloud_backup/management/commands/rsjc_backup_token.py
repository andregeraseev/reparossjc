import hashlib
import re
import secrets

from django.core.management.base import BaseCommand, CommandError

from cloud_backup.models import BackupAccount


class Command(BaseCommand):
    help = "Emite ou rotaciona o token de backup de uma conta."

    def add_arguments(self, parser):
        parser.add_argument("account")

    def handle(self, *args, **options):
        name = options["account"]
        if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
            raise CommandError("Use letras minúsculas, números e hífen.")
        token = secrets.token_urlsafe(32)
        BackupAccount.objects.update_or_create(name=name, defaults={
            "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "enabled": True,
        })
        self.stdout.write(token)
