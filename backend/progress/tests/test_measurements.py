"""Mensurations (spec 01 §19, spec 03 §10, spec 05 §12)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from progress.models import BodyMeasurementEntry

pytestmark = pytest.mark.django_db

MEASUREMENTS_URL = reverse("api-v1:progress:measurement-list")
TODAY = date(2026, 8, 26)


def detail_url(entry: BodyMeasurementEntry) -> str:
    return reverse("api-v1:progress:measurement-detail", args=[entry.pk])


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


def test_creation_de_mensurations(auth_client, active_user):
    response = auth_client.post(
        MEASUREMENTS_URL,
        {"date": TODAY.isoformat(), "waist_cm": "85.5", "body_fat_percent": "18.2"},
        format="json",
    )

    assert response.status_code == 201
    entry = BodyMeasurementEntry.objects.get(user=active_user)
    assert entry.waist_cm == Decimal("85.5")
    assert entry.body_fat_percent == Decimal("18.2")


def test_une_seule_entree_par_date(auth_client, active_user):
    """Une nouvelle saisie sur une date existante modifie (spec 01 §19)."""
    auth_client.post(MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "85"}, format="json")
    response = auth_client.post(
        MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "83"}, format="json"
    )

    assert response.status_code == 200
    assert BodyMeasurementEntry.objects.filter(user=active_user).count() == 1
    assert BodyMeasurementEntry.objects.get(user=active_user).waist_cm == Decimal("83")


def test_une_saisie_partielle_preserve_les_autres_mesures(auth_client, active_user):
    """Enregistrer un tour de taille n'efface pas la masse grasse du jour."""
    auth_client.post(
        MEASUREMENTS_URL,
        {"date": TODAY.isoformat(), "waist_cm": "85", "body_fat_percent": "18"},
        format="json",
    )
    auth_client.post(MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "83"}, format="json")

    entry = BodyMeasurementEntry.objects.get(user=active_user)
    assert entry.waist_cm == Decimal("83")
    assert entry.body_fat_percent == Decimal("18")


def test_une_entree_sans_aucune_mesure_est_refusee(auth_client):
    """Elle ne créerait qu'une ligne vide."""
    response = auth_client.post(
        MEASUREMENTS_URL, {"date": TODAY.isoformat(), "notes": "rien"}, format="json"
    )

    assert response.status_code == 400


def test_une_mesure_negative_est_refusee(auth_client):
    response = auth_client.post(
        MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "-5"}, format="json"
    )

    assert response.status_code == 400
    assert "waist_cm" in response.data["errors"]


def test_une_mesure_nulle_est_refusee(auth_client):
    """Zéro n'est pas une mesure : c'est une donnée manquante déguisée."""
    response = auth_client.post(
        MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "0"}, format="json"
    )

    assert response.status_code == 400
    assert "waist_cm" in response.data["errors"]


def test_une_masse_grasse_superieure_a_cent_est_refusee(auth_client):
    response = auth_client.post(
        MEASUREMENTS_URL,
        {"date": TODAY.isoformat(), "body_fat_percent": "120"},
        format="json",
    )

    assert response.status_code == 400
    assert "body_fat_percent" in response.data["errors"]


def test_une_mesure_absente_reste_nulle(auth_client):
    """`null`, jamais `0` (règle absolue du projet)."""
    response = auth_client.post(
        MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "85"}, format="json"
    )

    assert response.data["hips_cm"] is None
    assert response.data["body_fat_percent"] is None


def test_liste_antichronologique(auth_client, active_user):
    for offset in (0, -5, -2):
        BodyMeasurementEntry.objects.create(
            user=active_user, date=TODAY + timedelta(days=offset), waist_cm=Decimal("85")
        )

    dates = [row["date"] for row in auth_client.get(MEASUREMENTS_URL).data["results"]]

    assert dates == [
        TODAY.isoformat(),
        (TODAY - timedelta(days=2)).isoformat(),
        (TODAY - timedelta(days=5)).isoformat(),
    ]


def test_modification_dune_entree(auth_client, active_user):
    entry = BodyMeasurementEntry.objects.create(
        user=active_user, date=TODAY, waist_cm=Decimal("85")
    )

    response = auth_client.patch(detail_url(entry), {"waist_cm": "82"}, format="json")

    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.waist_cm == Decimal("82")


def test_une_modification_ne_peut_pas_vider_toutes_les_mesures(auth_client, active_user):
    entry = BodyMeasurementEntry.objects.create(
        user=active_user, date=TODAY, waist_cm=Decimal("85")
    )

    response = auth_client.patch(detail_url(entry), {"waist_cm": None}, format="json")

    assert response.status_code == 400


def test_suppression_dune_entree(auth_client, active_user):
    entry = BodyMeasurementEntry.objects.create(
        user=active_user, date=TODAY, waist_cm=Decimal("85")
    )

    assert auth_client.delete(detail_url(entry)).status_code == 204
    assert not BodyMeasurementEntry.objects.filter(pk=entry.pk).exists()


def test_les_mensurations_exigent_une_authentification(api_client):
    assert api_client.get(MEASUREMENTS_URL).status_code == 401


def test_un_utilisateur_ne_voit_que_ses_mensurations(active_user, other_user):
    BodyMeasurementEntry.objects.create(user=other_user, date=TODAY, waist_cm=Decimal("70"))

    assert client_for(active_user).get(MEASUREMENTS_URL).data["results"] == []


def test_un_utilisateur_ne_peut_pas_modifier_celles_dun_autre(active_user, other_user):
    entry = BodyMeasurementEntry.objects.create(user=other_user, date=TODAY, waist_cm=Decimal("70"))

    client = client_for(active_user)
    assert client.patch(detail_url(entry), {"waist_cm": "60"}, format="json").status_code == 404
    assert client.delete(detail_url(entry)).status_code == 404
    entry.refresh_from_db()
    assert entry.waist_cm == Decimal("70")


def test_deux_utilisateurs_peuvent_se_mesurer_le_meme_jour(active_user, other_user):
    for user in (active_user, other_user):
        response = client_for(user).post(
            MEASUREMENTS_URL, {"date": TODAY.isoformat(), "waist_cm": "85"}, format="json"
        )
        assert response.status_code == 201

    assert BodyMeasurementEntry.objects.count() == 2


def test_la_suppression_du_compte_emporte_les_mensurations(active_user):
    BodyMeasurementEntry.objects.create(user=active_user, date=TODAY, waist_cm=Decimal("85"))

    active_user.delete()

    assert BodyMeasurementEntry.objects.count() == 0
