import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from corporate.models import (
    Organization,
    OrganizationProvider,
    PartnerMembership,
    PortalChannel,
    PortalChannelMembership,
    ServiceProvider,
)


PORTALS = (
    {
        "organization_id": "org_cris_teste",
        "organization_slug": "cris-teste",
        "organization_name": "Cris Teste",
        "channel_id": "portal_cris_teste",
        "channel_slug": "teste",
        "display_name": "Cris Teste",
        "category": "Manutenção",
        "instructions": "Portal de homologação do fluxo de chamados da Reparos SJC.",
        "username": "portal_cris_teste",
        "password_env": "RSJC_PORTAL_CRIS_TESTE_PASSWORD",
        "sort_order": 0,
    },
    {
        "organization_id": "org_amil_demo",
        "organization_slug": "amil",
        "organization_name": "Amil",
        "channel_id": "portal_amil_juridico",
        "channel_slug": "juridico",
        "display_name": "Amil Jurídico",
        "category": "Jurídico",
        "instructions": "Informe unidade, responsável, endereço e o contexto do reparo solicitado pelo Jurídico.",
        "username": "portal_amil_juridico",
        "password_env": "RSJC_PORTAL_AMIL_JURIDICO_PASSWORD",
        "sort_order": 10,
    },
    {
        "organization_id": "org_amil_demo",
        "organization_slug": "amil",
        "organization_name": "Amil",
        "channel_id": "portal_amil_manutencao",
        "channel_slug": "manutencao",
        "display_name": "Amil Manutenção",
        "category": "Manutenção",
        "instructions": "Informe unidade, responsável local, sintomas e fotos que ajudem no orçamento.",
        "username": "portal_amil_manutencao",
        "password_env": "RSJC_PORTAL_AMIL_MANUTENCAO_PASSWORD",
        "sort_order": 20,
    },
    {
        "organization_id": "org_amil_demo",
        "organization_slug": "amil",
        "organization_name": "Amil",
        "channel_id": "portal_amil_distrato",
        "channel_slug": "distrato",
        "display_name": "Amil Distrato",
        "category": "Distrato",
        "instructions": "Informe o imóvel/unidade, responsável, itens de distrato e fotos do estado atual.",
        "username": "portal_amil_distrato",
        "password_env": "RSJC_PORTAL_AMIL_DISTRATO_PASSWORD",
        "sort_order": 30,
    },
)


class Command(BaseCommand):
    help = "Create/update the four v18.30 portal accounts. Passwords come only from environment variables."

    def add_arguments(self, parser):
        parser.add_argument("--provider-slug", default="reparos-sjc")

    @transaction.atomic
    def handle(self, *args, **options):
        missing = [row["password_env"] for row in PORTALS if not os.environ.get(row["password_env"], "")]
        if missing:
            raise CommandError("Missing password environment variable(s): " + ", ".join(missing))

        provider_slug = options["provider_slug"].strip() or "reparos-sjc"
        provider = ServiceProvider.objects.filter(slug=provider_slug, active=True).first()
        if provider is None:
            workspace_id = os.environ.get("RSJC_WORKSPACE_ID", "").strip()
            if not workspace_id:
                raise CommandError(
                    f"Provider {provider_slug!r} not found and RSJC_WORKSPACE_ID is not configured"
                )
            provider, _ = ServiceProvider.objects.update_or_create(
                id="provider_reparos_sjc",
                defaults={
                    "slug": provider_slug,
                    "name": "Reparos SJC",
                    "display_name": "Reparos SJC",
                    "workspace_id": workspace_id,
                    "active": True,
                },
            )

        User = get_user_model()
        created_names = []
        for row in PORTALS:
            org, _ = Organization.objects.update_or_create(
                id=row["organization_id"],
                defaults={
                    "slug": row["organization_slug"],
                    "name": row["organization_name"],
                    "display_name": row["organization_name"],
                    "demo": row["organization_slug"] == "cris-teste",
                    "active": True,
                },
            )
            OrganizationProvider.objects.update_or_create(
                organization=org,
                provider=provider,
                defaults={"active": True, "is_default": True, "sort_order": 0},
            )
            channel, _ = PortalChannel.objects.update_or_create(
                id=row["channel_id"],
                defaults={
                    "organization": org,
                    "slug": row["channel_slug"],
                    "display_name": row["display_name"],
                    "default_category": row["category"],
                    "instructions": row["instructions"],
                    "default_provider": provider,
                    "active": True,
                    "sort_order": row["sort_order"],
                },
            )
            user, _ = User.objects.get_or_create(username=row["username"])
            user.set_password(os.environ[row["password_env"]])
            user.is_active = True
            user.save(update_fields=["password", "is_active"])
            PartnerMembership.objects.update_or_create(
                user=user,
                organization=org,
                defaults={"role": "manager", "active": True},
            )
            PortalChannelMembership.objects.update_or_create(
                user=user,
                portal_channel=channel,
                defaults={"role": "manager", "active": True},
            )
            created_names.append(f"{row['display_name']}={row['username']}")

        self.stdout.write(self.style.SUCCESS("v18.30 portals ready: " + "; ".join(created_names)))
        self.stdout.write("Passwords were read from environment variables and were not printed or stored in source control.")
