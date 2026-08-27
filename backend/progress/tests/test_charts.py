"""Séries de progression (spec 01 §19, spec 04 §14).

Le lissage est le seul calcul de cette étape dont une erreur ne se voit pas :
une moyenne fausse reste plausible à l'écran. Ces tests le cadrent d'abord.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from progress.models import BodyMeasurementEntry, WeightEntry

pytestmark = pytest.mark.django_db

CHARTS_URL = reverse("api-v1:progress:charts")

#: Date de référence fixe : les tests ne doivent pas dépendre du jour où ils
#: tournent, sauf ceux qui vérifient précisément la période par défaut.
REFERENCE = date(2026, 8, 26)


def day(offset: int) -> str:
    return (REFERENCE + timedelta(days=offset)).isoformat()


def weigh(user: User, offset: int, kg: str) -> None:
    WeightEntry.objects.create(
        user=user, date=REFERENCE + timedelta(days=offset), weight_kg=Decimal(kg)
    )


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


def series(client: APIClient, **params) -> dict:
    params.setdefault("from", day(-60))
    params.setdefault("to", day(0))
    response = client.get(CHARTS_URL, params)
    assert response.status_code == 200, response.data
    return response.data


# --- Moyenne mobile ---------------------------------------------------------


def test_la_fenetre_est_calendaire_et_non_positionnelle(auth_client, active_user):
    """Trois pesées très espacées : chacune est seule dans sa fenêtre.

    Une moyenne portant sur « les sept dernières pesées » les mélangerait et
    lisserait deux mois comme s'il s'agissait d'une semaine.
    """
    weigh(active_user, -20, "80")
    weigh(active_user, -10, "79")
    weigh(active_user, -1, "78")

    points = series(auth_client)["points"]

    assert [point["moving_average"] for point in points] == ["80.00", "79.00", "78.00"]


def test_les_pesees_dune_meme_semaine_sont_moyennees(auth_client, active_user):
    weigh(active_user, -6, "80")
    weigh(active_user, -3, "79")
    weigh(active_user, 0, "78")

    points = series(auth_client)["points"]

    # Fenêtres successives : {80}, {80, 79}, {80, 79, 78}.
    assert [point["moving_average"] for point in points] == ["80.00", "79.50", "79.00"]


def test_une_pesee_hors_fenetre_est_exclue(auth_client, active_user):
    """La borne est à sept jours inclus : J-7 sort, J-6 reste."""
    weigh(active_user, -7, "90")
    weigh(active_user, -6, "76")
    weigh(active_user, 0, "80")

    points = series(auth_client)["points"]

    assert points[-1]["moving_average"] == "78.00"


def test_le_lissage_remonte_avant_le_debut_de_la_periode(auth_client, active_user):
    """La moyenne d'une date ne doit pas dépendre de la période demandée.

    Sans ce recul, la même pesée afficherait une moyenne sur une vue à
    trente jours et une autre sur une vue à quatre-vingt-dix.
    """
    weigh(active_user, -8, "80")
    weigh(active_user, -5, "76")

    points = series(auth_client, **{"from": day(-6)})["points"]

    # La pesée de J-8 n'est pas affichée mais appartient à la fenêtre de J-5.
    assert [point["date"] for point in points] == [day(-5)]
    assert points[0]["moving_average"] == "78.00"


def test_une_pesee_unique_est_sa_propre_moyenne(auth_client, active_user):
    weigh(active_user, 0, "80")

    data = series(auth_client)

    assert data["points"] == [{"date": day(0), "value": "80.00", "moving_average": "80.00"}]
    assert data["trend_per_week"] is None


def test_aucun_point_nest_fabrique_pour_les_jours_sans_pesee(auth_client, active_user):
    weigh(active_user, -30, "80")
    weigh(active_user, 0, "78")

    points = series(auth_client)["points"]

    assert [point["date"] for point in points] == [day(-30), day(0)]


def test_une_periode_sans_pesee_renvoie_une_serie_vide(auth_client, active_user):
    weigh(active_user, -50, "80")

    data = series(auth_client, **{"from": day(-10), "to": day(0)})

    assert data["points"] == []
    assert data["trend_per_week"] is None


# --- Tendance ---------------------------------------------------------------


def test_la_tendance_suit_une_perte_reguliere(auth_client, active_user):
    weigh(active_user, -14, "80")
    weigh(active_user, -7, "79")
    weigh(active_user, 0, "78")

    assert series(auth_client)["trend_per_week"] == "-1.00"


def test_la_tendance_suit_une_prise_reguliere(auth_client, active_user):
    weigh(active_user, -14, "78")
    weigh(active_user, -7, "79")
    weigh(active_user, 0, "80")

    assert series(auth_client)["trend_per_week"] == "1.00"


def test_la_tendance_est_nulle_sous_deux_points(auth_client, active_user):
    """`null`, pas zéro : zéro affirmerait une stagnation constatée."""
    weigh(active_user, 0, "80")

    assert series(auth_client)["trend_per_week"] is None


# --- Objectif ---------------------------------------------------------------


def test_lobjectif_de_poids_accompagne_la_serie(auth_client, active_user):
    active_user.profile.target_weight_kg = Decimal("70")
    active_user.profile.save()
    weigh(active_user, 0, "80")

    assert series(auth_client)["target"] == "70.00"


def test_labsence_dobjectif_ne_bloque_pas_la_serie(auth_client, active_user):
    weigh(active_user, 0, "80")

    assert series(auth_client)["target"] is None


# --- Métriques --------------------------------------------------------------


def test_une_mensuration_se_trace_comme_le_poids(auth_client, active_user):
    BodyMeasurementEntry.objects.create(
        user=active_user, date=REFERENCE + timedelta(days=-3), waist_cm=Decimal("85")
    )
    BodyMeasurementEntry.objects.create(user=active_user, date=REFERENCE, waist_cm=Decimal("83"))

    data = series(auth_client, metric="waist")

    assert data["unit"] == "cm"
    assert [point["value"] for point in data["points"]] == ["85.00", "83.00"]
    # Une mensuration n'a pas de cible : seul le poids en a une.
    assert data["target"] is None


def test_une_mesure_non_renseignee_est_absente_de_sa_serie(auth_client, active_user):
    """Une entrée partielle ne compte pas pour zéro dans les autres séries."""
    BodyMeasurementEntry.objects.create(user=active_user, date=REFERENCE, waist_cm=Decimal("85"))

    assert series(auth_client, metric="hips")["points"] == []


def test_une_metrique_inconnue_est_refusee(auth_client):
    response = auth_client.get(CHARTS_URL, {"metric": "humeur"})

    assert response.status_code == 400
    assert "metric" in response.data["errors"]


# --- Période ----------------------------------------------------------------


def test_la_periode_par_defaut_couvre_les_derniers_mois(auth_client):
    response = auth_client.get(CHARTS_URL)

    assert response.status_code == 200
    start = date.fromisoformat(response.data["from"])
    end = date.fromisoformat(response.data["to"])
    assert (end - start).days + 1 == 90


def test_un_debut_posterieur_a_la_fin_est_refuse(auth_client):
    response = auth_client.get(CHARTS_URL, {"from": day(0), "to": day(-10)})

    assert response.status_code == 400
    assert "from" in response.data["errors"]


def test_une_date_invalide_est_refusee(auth_client):
    response = auth_client.get(CHARTS_URL, {"from": "pas-une-date"})

    assert response.status_code == 400
    assert "from" in response.data["errors"]


def test_une_periode_de_plus_de_deux_ans_est_refusee(auth_client):
    response = auth_client.get(CHARTS_URL, {"from": day(-900), "to": day(0)})

    assert response.status_code == 400
    assert "from" in response.data["errors"]


# --- Permissions ------------------------------------------------------------


def test_la_serie_ne_montre_que_les_pesees_de_lappelant(auth_client, active_user, other_user):
    weigh(active_user, 0, "80")
    weigh(other_user, 0, "60")

    assert [point["value"] for point in series(auth_client)["points"]] == ["80.00"]
    assert [point["value"] for point in series(client_for(other_user))["points"]] == ["60.00"]


def test_la_serie_exige_une_authentification(api_client):
    assert api_client.get(CHARTS_URL).status_code == 401
