"""Disponibilité de l'IA annoncée à l'avance (spec 07 §11).

Cet endpoint existe pour une raison d'usage : apprendre qu'une fonctionnalité
est éteinte au moment où l'on envoie sa photo, après l'avoir cadrée, est une
mauvaise façon de l'apprendre.
"""

import pytest
from django.conf import settings as django_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from common.models import AppSetting

pytestmark = pytest.mark.django_db

STATUS_URL = reverse("api-v1:ai:status")


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[django_settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[django_settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


def test_l_ia_configuree_est_annoncee_disponible(ai_enabled, active_user):
    response = client_for(active_user).get(STATUS_URL)

    assert response.status_code == 200
    assert response.json() == {"enabled": True}


def test_l_ia_coupee_par_l_administrateur_est_annoncee_eteinte(ai_enabled, active_user):
    AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=False)

    assert client_for(active_user).get(STATUS_URL).json() == {"enabled": False}


def test_l_ia_non_deployee_est_annoncee_eteinte(ai_enabled, active_user):
    ai_enabled.AI_ENABLED = False

    assert client_for(active_user).get(STATUS_URL).json() == {"enabled": False}


def test_sans_cle_l_ia_est_annoncee_eteinte(ai_enabled, active_user):
    ai_enabled.AI_PROVIDER = "anthropic"
    ai_enabled.ANTHROPIC_API_KEY = ""

    assert client_for(active_user).get(STATUS_URL).json() == {"enabled": False}


def test_rien_d_autre_n_est_divulgue(ai_enabled, active_user):
    """Ni le fournisseur, ni le modèle, ni la présence d'une clé."""
    payload = client_for(active_user).get(STATUS_URL).json()

    assert set(payload) == {"enabled"}


def test_un_appel_anonyme_est_refuse(ai_enabled, db):
    assert APIClient().get(STATUS_URL).status_code == 401


def test_un_compte_suspendu_est_refuse(ai_enabled, db):
    suspendu = User.objects.create_user(
        username="suspendu", password="un-mot-de-passe-solide-1", status=UserStatus.SUSPENDED
    )

    assert client_for(suspendu).get(STATUS_URL).status_code == 401
