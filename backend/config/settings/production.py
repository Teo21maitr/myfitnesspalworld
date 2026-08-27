"""Réglages de production (spec 05 §13, spec 09 §8)."""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import CELERY_TASK_ALWAYS_EAGER, env

DEBUG = False

# Obligatoire : aucune valeur par défaut permissive en production.
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# Allowlist stricte, jamais "*".
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# HTTPS derrière le proxy Railway.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Si le frontend et l'API sont sur des sous-domaines distincts, SameSite=None
# est nécessaire — ce qui impose Secure=True.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=True)
AUTH_COOKIE_SAMESITE = env.str("AUTH_COOKIE_SAMESITE", default="None")

DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)

# En exécution synchrone, une requête tiendrait la connexion HTTP pendant tout
# le traitement qu'elle a déclenché.
if CELERY_TASK_ALWAYS_EAGER:
    raise ImproperlyConfigured("CELERY_TASK_ALWAYS_EAGER est interdit en production.")

# Sert les fichiers statiques de l'admin sans serveur web dédié.
MIDDLEWARE = [
    *MIDDLEWARE[:1],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
