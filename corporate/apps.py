from django.apps import AppConfig


class CorporateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "corporate"
    verbose_name = "Chamados corporativos"

    def ready(self):
        # Register compatibility signals only after Django has loaded models.
        from . import quote_compat  # noqa: F401
