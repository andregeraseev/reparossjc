from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from qa_monitor.models import LoginWindow, Session


class Command(BaseCommand):
    help = "Remove expired QA diagnostics and login counters from the isolated QA database."

    def handle(self, *args, **options):
        now = timezone.now()
        sessions, _ = Session.objects.filter(received_at__lt=now - timedelta(days=settings.RSJC_QA_RETENTION_DAYS)).delete()
        windows, _ = LoginWindow.objects.filter(started__lt=now - timedelta(days=1)).delete()
        self.stdout.write(f"Sessões removidas: {sessions}. Contadores removidos: {windows}.")
