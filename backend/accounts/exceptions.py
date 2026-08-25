"""Exceptions des endpoints publics d'authentification.

DRF transforme une `AuthenticationFailed` en 403 lorsque la vue ne déclare
aucune classe d'authentification, faute de pouvoir produire un en-tête
`WWW-Authenticate`. Les endpoints publics (connexion, refresh) ont pourtant
besoin d'un vrai 401 : ces exceptions le garantissent explicitement.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class AuthenticationError(APIException):
    """Échec d'authentification sur un endpoint public."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentification impossible."
    default_code = "authentication_failed"


class InvalidResetToken(APIException):
    """Lien de réinitialisation invalide, expiré ou déjà utilisé."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Ce lien de réinitialisation est invalide ou a expiré."
    default_code = "invalid_reset_token"
