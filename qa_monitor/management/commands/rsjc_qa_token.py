import hashlib
import re
import secrets

from django.core.management.base import BaseCommand, CommandError

from qa_monitor.models import Tester


class Command(BaseCommand):
    help = "Emite ou rotaciona a credencial de envio para um código fictício."

    def add_arguments(self, parser):
        parser.add_argument("code")

    def handle(self, *args, **options):
        code = options["code"]
        if not re.fullmatch(r"qa-[a-z0-9-]{1,45}", code):
            raise CommandError("Use um código fictício como qa-01.")
        token = secrets.token_urlsafe(32)
        Tester.objects.update_or_create(code=code, defaults={
            "token_hash": hashlib.sha256(token.encode("ascii")).hexdigest(), "enabled": True,
        })
        self.stdout.write(token)
