from django.core.management.base import BaseCommand

from support_center.services import purge_expired_support_data


class Command(BaseCommand):
    help = "Remove Support R1 telemetry beyond the configured retention windows."

    def handle(self, *args, **options):
        result = purge_expired_support_data()
        self.stdout.write(
            self.style.SUCCESS(
                "Support retention purge complete: "
                f"events={result['events']} snapshots={result['snapshots']} access_logs={result['accessLogs']}"
            )
        )
