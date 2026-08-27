"""Fixtures des tests de planification."""

import pytest

from accounts.models import User, UserStatus


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )
