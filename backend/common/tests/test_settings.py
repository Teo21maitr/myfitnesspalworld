"""Garde-fous de configuration (spec 07 §11, spec 09 §8).

Le piège de la mise en production : **une configuration absente ne doit jamais
produire un comportement plausible**.

Les deux premiers refus couvraient ce qui serait visiblement faux — un
fournisseur simulé, une exécution synchrone. Ceux qui suivent couvrent le vrai
danger : une variable oubliée qui laisse l'application *fonctionner*. Un lien de
réinitialisation vers `localhost` part, s'affiche comme envoyé, et n'ouvre rien.
Un backend email console écrit dans les journaux, et `EmailLog` dit « SENT ».

Aucune de ces fautes ne lève d'exception. C'est pourquoi le démarrage doit en
lever une.
"""

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
    "FRONTEND_URL": "https://app.example.com",
    "BACKEND_URL": "https://api.example.com",
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "DEFAULT_FROM_EMAIL": "bonjour@example.com",
}


BASE = "config.settings.base"


@pytest.fixture
def production_env(monkeypatch):
    """Environnement minimal pour importer les réglages de production.

    `config.settings.base` est retiré du cache d'imports puis restauré : sans
    cela, `production` lirait la valeur calculée au démarrage de la session de
    test et le garde-fou ne serait jamais éprouvé.

    La lecture du `.env` du dépôt est neutralisée. Sans cela, retirer une
    variable de l'environnement ne prouverait rien : le fichier la
    réalimenterait au ré-import, et le test passerait en croyant avoir éprouvé
    une absence. En production il n'y a pas de `.env` — la plateforme fournit
    l'environnement, ou ne le fournit pas.
    """
    import environ

    monkeypatch.setattr(environ.Env, "read_env", staticmethod(lambda *a, **k: None))

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


def test_le_fournisseur_simule_est_refuse_en_production(production_env):
    """Une suggestion inventée servie en production ne se verrait pas."""
    production_env.setenv("AI_PROVIDER", "fake")

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module(PRODUCTION)


def test_l_execution_synchrone_est_refusee_en_production(production_env):
    """Une requête HTTP y attendrait tout l'appel au modèle."""
    production_env.setenv("CELERY_TASK_ALWAYS_EAGER", "True")

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module(PRODUCTION)


def test_une_configuration_normale_est_acceptee(production_env):
    production_env.setenv("AI_PROVIDER", "anthropic")
    production_env.setenv("CELERY_TASK_ALWAYS_EAGER", "False")

    module = importlib.import_module(PRODUCTION)

    assert module.AI_PROVIDER == "anthropic"
    assert module.CELERY_TASK_ALWAYS_EAGER is False


class TestSilentAbsences:
    """Ce qui, absent, laisserait l'application marcher de travers."""

    @pytest.mark.parametrize(
        ("variable", "raison"),
        [
            pytest.param(
                "FRONTEND_URL",
                "les liens des emails pointeraient vers localhost",
                id="frontend-url",
            ),
            pytest.param(
                "BACKEND_URL",
                "les liens absolus pointeraient vers localhost",
                id="backend-url",
            ),
            pytest.param(
                "DEFAULT_FROM_EMAIL",
                "les emails partiraient de noreply@localhost",
                id="from-email",
            ),
            pytest.param(
                "EMAIL_BACKEND",
                "les emails partiraient dans stdout",
                id="email-backend",
            ),
        ],
    )
    def test_une_variable_manquante_empeche_le_demarrage(self, production_env, variable, raison):
        production_env.delenv(variable, raising=False)

        with pytest.raises(ImproperlyConfigured) as failure:
            importlib.import_module(PRODUCTION)

        message = str(failure.value)

        # `env.str` sans défaut lèverait déjà, en nommant la variable. Ce qui
        # se teste ici est le **message** : sans la raison, on saurait qu'il
        # manque quelque chose sans savoir ce qu'on risquait. C'est justement
        # la faute que cette étape combat, appliquée à son propre garde-fou.
        assert variable in message
        assert "production" in message, raison

    @pytest.mark.parametrize(
        "backend",
        [
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
        ],
    )
    def test_un_backend_email_sans_destinataire_est_refuse(self, production_env, backend):
        """`EmailLog` dirait « SENT » et personne ne recevrait rien."""
        production_env.setenv("EMAIL_BACKEND", backend)

        with pytest.raises(ImproperlyConfigured):
            importlib.import_module(PRODUCTION)

    def test_le_backend_smtp_est_accepte(self, production_env):
        module = importlib.import_module(PRODUCTION)

        assert module.EMAIL_BACKEND.endswith("smtp.EmailBackend")
        assert module.FRONTEND_URL == "https://app.example.com"

    def test_le_stockage_objet_reste_facultatif(self, production_env):
        """Son absence est bruyante : un envoi de photo répond 503 (étape 17)."""
        production_env.delenv("S3_BUCKET_NAME", raising=False)

        module = importlib.import_module(PRODUCTION)

        assert module.S3_BUCKET_NAME == ""
