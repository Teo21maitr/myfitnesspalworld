"""Garde-fous de configuration (spec 07 §11)."""

import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

PRODUCTION = "config.settings.production"

REQUIRED = {
    "DJANGO_SECRET_KEY": "cle-de-test-sans-valeur-de-securite",
    "DJANGO_ALLOWED_HOSTS": "example.com",
    "CORS_ALLOWED_ORIGINS": "https://example.com",
    "CSRF_TRUSTED_ORIGINS": "https://example.com",
}


BASE = "config.settings.base"


@pytest.fixture
def production_env(monkeypatch):
    """Environnement minimal pour importer les réglages de production.

    `config.settings.base` est retiré du cache d'imports puis restauré : sans
    cela, `production` lirait la valeur calculée au démarrage de la session de
    test et le garde-fou ne serait jamais éprouvé.
    """
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)

    original_base = sys.modules.pop(BASE, None)
    sys.modules.pop(PRODUCTION, None)
    try:
        yield monkeypatch
    finally:
        sys.modules.pop(PRODUCTION, None)
        if original_base is not None:
            sys.modules[BASE] = original_base


def test_l_execution_synchrone_est_refusee_en_production(production_env):
    """Une requête HTTP y attendrait tout l'appel au modèle."""
    production_env.setenv("CELERY_TASK_ALWAYS_EAGER", "True")

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module(PRODUCTION)


def test_une_configuration_normale_est_acceptee(production_env):
    production_env.setenv("CELERY_TASK_ALWAYS_EAGER", "False")

    module = importlib.import_module(PRODUCTION)

    assert module.CELERY_TASK_ALWAYS_EAGER is False
