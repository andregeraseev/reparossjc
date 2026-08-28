from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from corporate.models import Organization, OrganizationProvider, PartnerMembership, PortalChannel, ServiceProvider


class Command(BaseCommand):
    help = "Cria ou atualiza um canal de portal corporativo sem lidar com senhas ou tokens."

    def add_arguments(self, parser):
        parser.add_argument("--organization-slug", required=True)
        parser.add_argument("--organization-name", required=True)
        parser.add_argument("--portal-slug", required=True)
        parser.add_argument("--portal-name", required=True)
        parser.add_argument("--category", default="Manutenção")
        parser.add_argument("--instructions", default="")
        parser.add_argument("--provider-slug", default="")
        parser.add_argument("--username", default="")

    @transaction.atomic
    def handle(self, *args, **options):
        organization_slug = slugify(options["organization_slug"])[:80]
        portal_slug = slugify(options["portal_slug"])[:80]
        if not organization_slug or not portal_slug:
            raise CommandError("Os slugs da empresa e do portal precisam conter letras ou números.")

        organization, created = Organization.objects.get_or_create(
            slug=organization_slug,
            defaults={
                "id": "org_" + uuid4().hex[:20],
                "name": options["organization_name"][:160],
                "display_name": options["organization_name"][:160],
                "active": True,
            },
        )
        if not organization.active:
            raise CommandError("A empresa existe, mas está inativa.")

        provider = None
        provider_slug = slugify(options["provider_slug"])[:80]
        if provider_slug:
            provider = ServiceProvider.objects.filter(slug=provider_slug, active=True).first()
            if provider is None:
                raise CommandError(f"Prestador ativo não encontrado: {provider_slug}")
            provider_link, _ = OrganizationProvider.objects.get_or_create(
                organization=organization,
                provider=provider,
                defaults={"active": True, "is_default": not organization.provider_links.filter(active=True, is_default=True).exists()},
            )
            if not provider_link.active:
                provider_link.active = True
                provider_link.save(update_fields=["active"])

        channel = PortalChannel.objects.filter(organization=organization, slug=portal_slug).first()
        channel_created = channel is None
        if channel is None:
            channel = PortalChannel(id="PC" + uuid4().hex[:22], organization=organization, slug=portal_slug)
        channel.display_name = options["portal_name"][:160]
        channel.default_category = (options["category"] or "Manutenção")[:120]
        channel.instructions = options["instructions"][:300]
        channel.active = True
        if provider is not None:
            channel.default_provider = provider
        channel.save()

        username = options["username"].strip()
        if username:
            user = get_user_model().objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"Usuário existente não encontrado: {username}")
            PartnerMembership.objects.update_or_create(
                user=user,
                organization=organization,
                defaults={"role": "manager", "active": True},
            )

        state = "criado" if channel_created else "atualizado"
        org_state = "nova empresa" if created else "empresa existente"
        self.stdout.write(self.style.SUCCESS(f"Portal {state}: {channel.display_name} ({org_state})"))
        self.stdout.write(f"Caminho: /corporativo/p/{organization.slug}/{channel.slug}/")
