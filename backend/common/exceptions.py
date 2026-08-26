"""Format d'erreur unique de l'API (spec 10 §5).

Toute erreur gérée renvoie :

    {"code": "...", "message": "...", "errors": {...}}
"""

import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

NON_FIELD_KEY = "non_field_errors"

DEFAULT_MESSAGES = {
    400: "Requête invalide.",
    401: "Authentification requise.",
    403: "Vous n'avez pas la permission d'effectuer cette action.",
    404: "Ressource introuvable.",
    405: "Méthode non autorisée.",
    415: "Format de requête non supporté.",
    429: "Trop de requêtes. Réessayez plus tard.",
    500: "Une erreur interne est survenue.",
}


def _flatten(value: Any) -> list[str]:
    """Réduit une structure d'erreurs DRF en liste de messages."""
    if isinstance(value, list):
        return [message for item in value for message in _flatten(item)]
    if isinstance(value, dict):
        return [
            f"{key}: {message}" for key, nested in value.items() for message in _flatten(nested)
        ]
    return [str(value)]


def _normalize_errors(detail: Any) -> dict[str, list[str]]:
    """Normalise le détail d'une ValidationError en `champ -> messages`."""
    if isinstance(detail, dict):
        return {str(field): _flatten(value) for field, value in detail.items()}
    return {NON_FIELD_KEY: _flatten(detail)}


def api_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Handler d'exception DRF renvoyant le format d'erreur du projet."""
    # Les services métier lèvent la `ValidationError` de Django, qui est leur
    # exception idiomatique. Sans cette conversion, DRF ne la reconnaîtrait pas
    # et une règle métier violée produirait un 500 au lieu d'un 400.
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)

    response = drf_exception_handler(exc, context)

    if response is None:
        # Exception non gérée : on laisse Django produire une 500 et on
        # journalise sans exposer de détail technique au client.
        logger.exception(
            "Exception non gérée sur %s",
            getattr(context.get("request"), "path", "?"),
        )
        return None

    status_code = response.status_code
    detail = response.data
    code = getattr(exc, "default_code", None) or "error"
    errors: dict[str, list[str]] = {}

    if isinstance(exc, ValidationError):
        code = "validation_error"
        message = "Données invalides."
        errors = _normalize_errors(detail)
    elif isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        code = getattr(detail["detail"], "code", code)
    else:
        message = DEFAULT_MESSAGES.get(status_code, "Une erreur est survenue.")
        errors = _normalize_errors(detail)

    response.data = {"code": code, "message": message, "errors": errors}
    return response
