"""Réglages de développement local."""

from .base import *
from .base import FRONTEND_URL, env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# `backend` est le nom du service dans docker compose.
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "backend"],
)

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
)

# En local, frontend et backend partagent le site `localhost` : Lax suffit et
# évite d'imposer des cookies Secure sur du HTTP.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=False)
AUTH_COOKIE_SAMESITE = env.str("AUTH_COOKIE_SAMESITE", default="Lax")

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

EMAIL_BACKEND = env.str("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# L'interface DRF navigable est utile en développement uniquement.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}
