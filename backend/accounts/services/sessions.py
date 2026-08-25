"""Émission et révocation des sessions d'authentification.

Ce module est le seul endroit qui connaît le nom et les attributs des
cookies d'authentification, ainsi que le mécanisme de révocation.
"""

from django.conf import settings
from django.db.models import F
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User

# Claim portant la version de session de l'utilisateur. Un token dont la
# version diffère de celle en base est refusé, ce qui rend la déconnexion
# globale immédiate — y compris pour les access tokens déjà émis.
# S105 : il s'agit du nom d'un claim JWT, pas d'un secret.
TOKEN_VERSION_CLAIM = "tv"  # noqa: S105


def build_refresh_token(user: User) -> RefreshToken:
    """Crée un refresh token portant la version de session courante.

    Le claim est posé avant de dériver l'access token afin qu'il y soit copié
    (`RefreshToken.access_token` recopie les claims non exclus).
    """
    refresh = RefreshToken.for_user(user)
    refresh[TOKEN_VERSION_CLAIM] = user.token_version
    return refresh


def revoke_all_sessions(user: User) -> None:
    """Invalide immédiatement toutes les sessions de l'utilisateur.

    Deux mécanismes complémentaires :

    1. l'incrément de `token_version` invalide les access tokens déjà émis,
       que SimpleJWT ne sait pas révoquer puisqu'ils sont sans état ;
    2. la mise en liste noire des refresh tokens empêche leur réutilisation et
       laisse une trace en base.
    """
    User.objects.filter(pk=user.pk).update(token_version=F("token_version") + 1)
    user.refresh_from_db(fields=["token_version"])

    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


def set_auth_cookies(response: Response, refresh: RefreshToken) -> Response:
    """Pose les cookies HttpOnly d'access et de refresh."""
    common = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "domain": settings.AUTH_COOKIE_DOMAIN,
    }

    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        str(refresh.access_token),
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_COOKIE_PATH,
        **common,
    )
    # Le cookie de refresh n'est envoyé qu'aux routes d'authentification : il
    # ne circule donc pas à chaque appel d'API.
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        **common,
    )
    return response


def clear_auth_cookies(response: Response) -> Response:
    """Efface les cookies d'authentification."""
    response.delete_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        path=settings.AUTH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response
