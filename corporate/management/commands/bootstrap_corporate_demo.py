import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from corporate.models import Organization, OrganizationProvider, PartnerMembership, ServiceProvider


class Command(BaseCommand):
    help = "Create/update the Amil production organization and its portal user from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("RSJC_AMIL_USERNAME", "").strip()
        password = os.environ.get("RSJC_AMIL_PASSWORD", "")
        email = os.environ.get("RSJC_AMIL_EMAIL", "").strip()
        if not username or not password:
            raise CommandError("RSJC_AMIL_USERNAME and RSJC_AMIL_PASSWORD are required")

        # Keep the historical primary key so existing requests/memberships are not
        # broken, but promote the organization identity from demo to production.
        org, _ = Organization.objects.update_or_create(
            id="org_amil_demo",
            defaults={
                "slug": "amil",
                "name": "Amil",
                "display_name": "Amil",
                "demo": False,
                "active": True,
            },
        )
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        if email and user.email != email:
            user.email = email
        user.set_password(password)
        user.is_active = True
        user.save()
        PartnerMembership.objects.update_or_create(
            user=user,
            organization=org,
            defaults={"role": "manager", "active": True},
        )
        workspace_id = os.environ.get("RSJC_WORKSPACE_ID", "").strip()
        if not workspace_id:
            raise CommandError("RSJC_WORKSPACE_ID is required")
        provider, _ = ServiceProvider.objects.update_or_create(
            id="provider_reparos_sjc",
            defaults={
                "slug": "reparos-sjc",
                "name": "Reparos SJC",
                "display_name": "Reparos SJC",
                "workspace_id": workspace_id,
                "active": True,
            },
        )
        OrganizationProvider.objects.update_or_create(
            organization=org,
            provider=provider,
            defaults={"active": True, "is_default": True, "sort_order": 0},
        )
        self.stdout.write(self.style.SUCCESS(f"Amil portal ready for user {username} ({'created' if created else 'updated'})"))
