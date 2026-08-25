"""Configuration pytest partagée."""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isole les tests du throttling DRF, qui s'appuie sur le cache.

    Sans cela, les tentatives de connexion s'accumuleraient d'un test à
    l'autre et déclencheraient une 429 fortuite.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def active_user(db):
    """Utilisateur ACTIVE prêt à être authentifié."""
    from accounts.models import User, UserStatus

    return User.objects.create_user(
        username="teo",
        password="motdepasse-de-test-123",
        status=UserStatus.ACTIVE,
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(active_user):
    """Client authentifié par cookies, comme le fait le navigateur.

    Instancie son propre client plutôt que de réutiliser `api_client` : les
    tests qui comparent deux appareils ont besoin de deux clients distincts.
    """
    from django.conf import settings
    from rest_framework.test import APIClient

    from accounts.services.sessions import build_refresh_token

    client = APIClient()
    refresh = build_refresh_token(active_user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client
