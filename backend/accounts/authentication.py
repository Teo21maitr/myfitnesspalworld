"""Authentification par cookie HttpOnly.

Les tokens JWT ne transitent jamais par `localStorage` (spec 05 §5) : le
frontend n'y a pas accès et le navigateur renvoie automatiquement le cookie.
"""

from django.conf import settings
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Lit l'access token dans un cookie HttpOnly.

    L'en-tête `Authorization` reste accepté en repli, ce qui est utile pour
    les outils de développement et les tests d'API ; il n'affaiblit rien
    puisque le token doit de toute façon être valide.
    """

    def authenticate(self, request: Request):
        header = self.get_header(request)
        raw_token = (
            self.get_raw_token(header)
            if header is not None
            else request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        )
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
