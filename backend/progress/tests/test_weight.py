"""Suivi du poids (spec 01 §19, spec 04 §14)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from progress.models import WeightEntry

pytestmark = pytest.mark.django_db

WEIGHT_URL = reverse("api-v1:progress:weight-list")


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def test_creation_dune_pesee(auth_client, active_user):
    response = auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80.50"})

    assert response.status_code == 201
    entry = WeightEntry.objects.get(user=active_user)
    assert entry.weight_kg == Decimal("80.50")


def test_une_seule_pesee_par_date(auth_client, active_user):
    """Une nouvelle saisie sur la même date met à jour l'entrée (spec 01 §19)."""
    auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80.50"})

    response = auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "79.80"})

    assert response.status_code == 200
    assert WeightEntry.objects.filter(user=active_user).count() == 1
    assert WeightEntry.objects.get(user=active_user).weight_kg == Decimal("79.80")


def test_plusieurs_dates_coexistent(auth_client, active_user):
    auth_client.post(WEIGHT_URL, {"date": "2026-08-23", "weight_kg": "81.00"})
    auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80.50"})

    assert WeightEntry.objects.filter(user=active_user).count() == 2


def test_liste_antichronologique(auth_client, active_user):
    auth_client.post(WEIGHT_URL, {"date": "2026-08-23", "weight_kg": "81.00"})
    auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80.50"})

    results = auth_client.get(WEIGHT_URL).json()["results"]

    assert results[0]["date"] == "2026-08-24"


def test_un_poids_negatif_est_refuse(auth_client):
    response = auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "-5"})

    assert response.status_code == 400
    assert "weight_kg" in response.json()["errors"]


def test_modification_dune_pesee(auth_client, active_user):
    auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80.50"})
    entry = WeightEntry.objects.get(user=active_user)
    url = reverse("api-v1:progress:weight-detail", args=[entry.pk])

    response = auth_client.patch(url, {"weight_kg": "79.00"})

    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.weight_kg == Decimal("79.00")


def test_suppression_dune_pesee(auth_client, active_user):
    auth_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80.50"})
    entry = WeightEntry.objects.get(user=active_user)

    response = auth_client.delete(reverse("api-v1:progress:weight-detail", args=[entry.pk]))

    assert response.status_code == 204
    assert WeightEntry.objects.count() == 0


def test_le_suivi_exige_une_authentification(api_client):
    assert api_client.get(WEIGHT_URL).status_code == 401
    assert api_client.post(WEIGHT_URL, {"date": "2026-08-24", "weight_kg": "80"}).status_code == 401


def test_un_utilisateur_ne_voit_que_ses_pesees(active_user, other_user):
    WeightEntry.objects.create(user=active_user, date=date.today(), weight_kg=Decimal("80"))

    assert client_for(other_user).get(WEIGHT_URL).json()["count"] == 0


def test_un_utilisateur_ne_peut_pas_modifier_la_pesee_dun_autre(active_user, other_user):
    entry = WeightEntry.objects.create(user=active_user, date=date.today(), weight_kg=Decimal("80"))
    url = reverse("api-v1:progress:weight-detail", args=[entry.pk])

    assert client_for(other_user).patch(url, {"weight_kg": "50"}).status_code == 404
    entry.refresh_from_db()
    assert entry.weight_kg == Decimal("80.00")


def test_deux_utilisateurs_peuvent_peser_le_meme_jour(active_user, other_user):
    today = date.today()
    WeightEntry.objects.create(user=active_user, date=today, weight_kg=Decimal("80"))
    WeightEntry.objects.create(user=other_user, date=today, weight_kg=Decimal("65"))

    assert WeightEntry.objects.count() == 2


def test_la_suppression_du_compte_emporte_les_pesees(active_user):
    WeightEntry.objects.create(
        user=active_user, date=date.today() - timedelta(days=1), weight_kg=Decimal("80")
    )

    active_user.delete()

    assert WeightEntry.objects.count() == 0
