"""Fixtures partagées des tests sociaux."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


def make_user(username: str) -> User:
    return User.objects.create_user(
        username=username, password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def alice(db) -> User:
    return make_user("alice")


@pytest.fixture
def bob(db) -> User:
    return make_user("bob")


@pytest.fixture
def carol(db) -> User:
    return make_user("carol")
