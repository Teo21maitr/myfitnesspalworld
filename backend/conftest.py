"""Configuration pytest partagée."""

import pytest


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
