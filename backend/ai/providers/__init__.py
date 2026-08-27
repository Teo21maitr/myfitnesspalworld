"""Fournisseurs d'IA et sélection de celui en service (spec 07 §2)."""

from django.conf import settings

from .base import (
    AIProvider,
    AIProviderError,
    AIProviderUnavailable,
    AIResponseUnusable,
    ImagePart,
)

__all__ = [
    "AIProvider",
    "AIProviderError",
    "AIProviderUnavailable",
    "AIResponseUnusable",
    "ImagePart",
    "get_provider",
]


def get_provider() -> AIProvider:
    """Instancie le fournisseur désigné par `AI_PROVIDER`.

    Les imports sont faits ici plutôt qu'en tête de module : charger le SDK
    Anthropic dans un processus qui tourne avec le fournisseur simulé n'aurait
    aucun sens.
    """
    if settings.AI_PROVIDER == "fake":
        from .fake import FakeProvider

        return FakeProvider()

    from .anthropic import AnthropicProvider

    return AnthropicProvider()
