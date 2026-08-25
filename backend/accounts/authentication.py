"""Authentification par cookie HttpOnly.

Les tokens JWT ne transitent jamais par `localStorage` (spec 05 §5) : le
frontend n'y a pas accès et le navigateur renvoie automatiquement le cookie.

Une authentification portée par un cookie est une authentification
« ambiante » : elle est donc vulnérable au CSRF, que DRF n'applique pas à ses
vues par défaut. Cette classe rétablit la vérification, comme le fait
`SessionAuthentication`.
"""

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.services.sessions import TOKEN_VERSION_CLAIM


class CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


class CookieJWTAuthentication(JWTAuthentication):
    """Lit l'access token dans un cookie HttpOnly et applique le CSRF.

    L'en-tête `Authorization: Bearer` reste accepté pour les outils de
    développement et les tests d'API ; il est dispensé de CSRF puisqu'il n'est
    pas envoyé automatiquement par le navigateur.
    """

    def authenticate(self, request: Request):
        header = self.get_header(request)

        if header is not None:
            raw_token = self.get_raw_token(header)
            from_cookie = False
        else:
            raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
            from_cookie = True

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        if from_cookie:
            self.enforce_csrf(request)

        return user, validated_token

    def get_user(self, validated_token):
        """Refuse un token émis avant une révocation globale des sessions.

        SimpleJWT ne sait invalider que les refresh tokens ; ce contrôle rend
        la déconnexion globale et le changement de mot de passe effectifs
        immédiatement, y compris pour les access tokens déjà en circulation.
        """
        user = super().get_user(validated_token)

        if validated_token.get(TOKEN_VERSION_CLAIM) != user.token_version:
            raise exceptions.AuthenticationFailed(
                "Votre session a été révoquée. Reconnectez-vous.",
                code="session_revoked",
            )

        return user

    def enforce_csrf(self, request: Request) -> None:
        """Applique la vérification CSRF de Django aux méthodes non sûres."""

        def dummy_get_response(request):  # pragma: no cover - jamais appelé
            return None

        check = CSRFCheck(dummy_get_response)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"Échec de la vérification CSRF : {reason}")
