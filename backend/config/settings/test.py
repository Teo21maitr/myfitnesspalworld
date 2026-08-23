"""Réglages utilisés par pytest et la CI."""

from .base import *

DEBUG = False

SECRET_KEY = "test-secret-key-not-used-outside-tests"  # noqa: S105

ALLOWED_HOSTS = ["*"]

# Hachage rapide : les tests ne valident pas la robustesse d'Argon2/PBKDF2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Aucun accès réseau involontaire depuis les tests.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
