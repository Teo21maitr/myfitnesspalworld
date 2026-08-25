from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Comptes"

    def ready(self) -> None:
        from . import signals  # noqa: F401 - enregistrement des récepteurs
