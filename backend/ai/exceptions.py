"""Erreurs d'API propres à l'IA."""

from rest_framework.exceptions import APIException


class AIUnavailable(APIException):
    """L'IA n'est pas disponible (spec 07 §11).

    503 et non 500 : ce n'est pas un défaut de l'application mais un service
    absent — coupé par un administrateur, non configuré, ou en panne. Le reste
    de l'application continue de fonctionner normalement.
    """

    status_code = 503
    default_detail = "L'analyse par IA est momentanément indisponible."
    default_code = "ai_disabled"
