from django.apps import AppConfig


class ProviderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'provider'

    def ready(self):
        """Import signals when Django starts"""
        import provider.signals  # noqa: F401
