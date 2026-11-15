import re
import secrets

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from qa_monitor.models import StaffAccount


class Command(BaseCommand):
    help = "Cria acesso individual para a equipe do painel de QA."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        username = options["username"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,47}", username):
            raise CommandError("Use de 2 a 48 caracteres em letras minúsculas, números, hífen ou sublinhado.")
        password = secrets.token_urlsafe(24)
        try:
            StaffAccount.objects.create(username=username, password_hash=make_password(password))
        except IntegrityError as exc:
            raise CommandError("Esse usuário de QA já existe.") from exc
        self.stdout.write(password)
