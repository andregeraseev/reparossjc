import hashlib
import os

from django.core.management.base import BaseCommand, CommandError

from corporate.models import ServiceProvider


class Command(BaseCommand):
    help = "Store the SHA-256 hash of a provider token read from a private environment variable."

    def add_arguments(self, parser):
        parser.add_argument("provider_slug")
        parser.add_argument("--token-env", default="RSJC_PROVIDER_TOKEN")

    def handle(self, *args, **options):
        env_name = options["token_env"].strip()
        token = os.environ.get(env_name, "")
        if len(token) < 24:
            raise CommandError(f"{env_name} must contain a private token with at least 24 characters")
        try:
            provider = ServiceProvider.objects.get(slug=options["provider_slug"], active=True)
        except ServiceProvider.DoesNotExist as exc:
            raise CommandError("Active provider not found") from exc
        provider.operator_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        provider.save(update_fields=["operator_token_hash", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Token hash updated for provider {provider.slug}"))
