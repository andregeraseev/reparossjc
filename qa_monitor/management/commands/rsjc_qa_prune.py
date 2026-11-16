from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from qa_monitor.models import BugReport, LoginWindow, Session, StaffSession


class Command(BaseCommand):
    help = "Remove expired QA diagnostics and login counters from the isolated QA database."

    def handle(self, *args, **options):
        now = timezone.now()
        sessions, _ = Session.objects.filter(received_at__lt=now - timedelta(days=settings.RSJC_QA_RETENTION_DAYS)).delete()
        bugs, _ = BugReport.objects.filter(received_at__lt=now - timedelta(days=settings.RSJC_QA_RETENTION_DAYS)).delete()
        windows, _ = LoginWindow.objects.filter(started__lt=now - timedelta(days=1)).delete()
        logins, _ = StaffSession.objects.filter(expires_at__lte=now).delete()
        self.stdout.write(f"Sessões removidas: {sessions}. Relatos removidos: {bugs}. Contadores removidos: {windows}. Acessos vencidos: {logins}.")
