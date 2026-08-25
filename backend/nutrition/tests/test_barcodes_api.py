"""Endpoints code-barres et recherche élargie (spec 04 §3, spec 11 §4).

L'ordre de résolution est la règle métier centrale : aliment personnel, puis
cache local, puis seulement la source externe. Chaque étape franchie de trop
coûte une part du quota partagé par tous les comptes.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest
import responses
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from nutrition.models import Food, FoodNutrition, FoodSource, UnitType

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "off"

BARCODE = "3017620422003"
PRODUCT_URL = f"{settings.OFF_PRODUCT_URL}/api/v3/product/{BARCODE}.json"
SEARCH_URL = f"{settings.OFF_SEARCH_URL}/search"

LOOKUP_URL = reverse("api-v1:barcodes:lookup", args=[BARCODE])
EXTERNAL_SEARCH_URL = reverse("api-v1:foods:external-search")


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def cached_product(db) -> Food:
    """Produit Open Food Facts déjà rapatrié et frais."""
    food = Food.objects.create(
        source=FoodSource.OFF,
        external_id=BARCODE,
        barcode=BARCODE,
        name="Nutella",
        brand="Nutella",
        reference_unit=UnitType.GRAM,
        cache_refreshed_at=timezone.now(),
    )
    FoodNutrition.objects.create(food=food, energy_kcal="539")
    return food


# --- Ordre de résolution -----------------------------------------------------


@responses.activate
def test_l_aliment_personnel_prime_sur_la_source_externe(auth_client, active_user):
    """L'utilisateur qui a créé sa propre version doit la retrouver."""
    own = Food.objects.create(
        source=FoodSource.USER,
        owner=active_user,
        barcode=BARCODE,
        name="Ma pâte à tartiner",
    )
    FoodNutrition.objects.create(food=own, energy_kcal="500")

    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 200
    assert response.data["id"] == own.id
    assert len(responses.calls) == 0


@responses.activate
def test_un_produit_en_cache_est_servi_sans_appel_sortant(auth_client, cached_product):
    """C'est tout l'intérêt du cache : ne pas redépenser de quota."""
    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 200
    assert response.data["id"] == cached_product.id
    assert len(responses.calls) == 0


@responses.activate
def test_un_produit_inconnu_localement_est_rapatrie_puis_mis_en_cache(auth_client):
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)

    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 200
    assert response.data["name"] == "Nutella"
    assert response.data["source"] == FoodSource.OFF
    assert Food.objects.filter(source=FoodSource.OFF, external_id=BARCODE).exists()


@responses.activate
def test_le_second_appel_ne_redeclenche_pas_la_source(auth_client):
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)

    auth_client.get(LOOKUP_URL)
    auth_client.get(LOOKUP_URL)

    assert len(responses.calls) == 1


# --- Produit introuvable -----------------------------------------------------


@responses.activate
def test_un_code_inconnu_repond_404_avec_un_code_exploitable(auth_client):
    """Le frontend s'en sert pour proposer la création manuelle (spec 01 §10)."""
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_not_found.json"), status=404)

    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 404
    assert response.data["code"] == "product_not_found"


# --- Panne de la source ------------------------------------------------------


@responses.activate
def test_une_panne_de_la_source_repond_503_et_non_404(auth_client):
    """Confondre les deux ferait créer des doublons de produits existants."""
    responses.add(responses.GET, PRODUCT_URL, body="<html>indisponible</html>", status=200)

    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 503
    assert response.data["code"] == "external_source_unavailable"


@responses.activate
def test_la_source_desactivee_repond_503(auth_client, settings):
    settings.OFF_ENABLED = False

    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 503
    assert len(responses.calls) == 0


# --- Validation avant dépense de quota ---------------------------------------


@pytest.mark.parametrize(
    "barcode",
    ["1234567", "1" * 25, "30176204220ab", "abcdefgh"],
    ids=["trop-court", "trop-long", "lettres-melees", "lettres"],
)
@responses.activate
def test_un_code_barres_invalide_est_rejete_avant_tout_appel(auth_client, barcode):
    url = reverse("api-v1:barcodes:lookup", args=[barcode])

    response = auth_client.get(url)

    assert response.status_code == 400
    assert response.data["code"] == "invalid_barcode"
    assert len(responses.calls) == 0


@responses.activate
def test_un_code_plus_long_que_les_standards_est_accepte(auth_client):
    """Open Food Facts référence des codes de plus de 14 chiffres.

    Les rejeter rendrait ces produits impossibles à ouvrir depuis la recherche
    élargie, alors qu'ils y apparaissent.
    """
    long_code = "990530101015842243"
    url = reverse("api-v1:barcodes:lookup", args=[long_code])
    responses.add(
        responses.GET,
        f"{settings.OFF_PRODUCT_URL}/api/v3/product/{long_code}.json",
        json={"product": {"code": long_code, "product_name": "Chocapic", "nutriments": {}}},
        status=200,
    )

    response = auth_client.get(url)

    assert response.status_code == 200


# --- Permissions -------------------------------------------------------------


def test_un_visiteur_anonyme_est_refuse(api_client):
    assert api_client.get(LOOKUP_URL).status_code == 401


def test_un_compte_non_actif_est_refuse(db):
    """Un compte PENDING n'a `is_active` à vrai que s'il est ACTIVE (spec 05 §2).

    Le rejet intervient donc dès l'authentification, avant même la permission
    `IsActiveAccount` qui reste la seconde barrière.
    """
    user = User.objects.create_user(
        username="attente", password="un-mot-de-passe-solide-1", status=UserStatus.PENDING
    )
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)

    assert client.get(LOOKUP_URL).status_code == 401


def test_une_fiche_rapatriee_n_est_pas_modifiable(auth_client, cached_product):
    """Régression : les fiches externes restent en lecture seule (spec 05 §6)."""
    url = reverse("api-v1:foods:detail", args=[cached_product.id])

    response = auth_client.patch(url, {"name": "Autre nom"})

    assert response.status_code == 403
    cached_product.refresh_from_db()
    assert cached_product.name == "Nutella"


# --- Rafraîchissement du cache -----------------------------------------------


@responses.activate
def test_une_fiche_perimee_est_rafraichie_en_tache_de_fond(auth_client, cached_product):
    """L'utilisateur reçoit la fiche en cache sans attendre le réseau."""
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)
    stale = timezone.now() - timedelta(days=settings.OFF_CACHE_TTL_DAYS + 1)
    Food.objects.filter(pk=cached_product.pk).update(cache_refreshed_at=stale)

    response = auth_client.get(LOOKUP_URL)

    assert response.status_code == 200
    # `CELERY_TASK_ALWAYS_EAGER` exécute la tâche immédiatement en test.
    cached_product.refresh_from_db()
    assert cached_product.cache_refreshed_at > stale


@responses.activate
def test_une_fiche_fraiche_ne_declenche_aucun_rafraichissement(auth_client, cached_product):
    auth_client.get(LOOKUP_URL)

    assert len(responses.calls) == 0


# --- Recherche élargie -------------------------------------------------------


@responses.activate
def test_la_recherche_elargie_renvoie_des_candidats(auth_client):
    responses.add(responses.GET, SEARCH_URL, json=fixture("search_nutella.json"), status=200)

    response = auth_client.get(EXTERNAL_SEARCH_URL, {"q": "nutella"})

    assert response.status_code == 200
    assert len(response.data["results"]) == 3
    assert response.data["results"][0]["code"] == "0009800800049"


@responses.activate
def test_un_candidat_deja_en_base_porte_son_identifiant(auth_client, cached_product):
    """Permet d'ouvrir la fiche sans redépenser de quota."""
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={"hits": [{"code": BARCODE, "product_name": "Nutella", "brands": ["Nutella"]}]},
        status=200,
    )

    response = auth_client.get(EXTERNAL_SEARCH_URL, {"q": "nutella"})

    assert response.data["results"][0]["food_id"] == cached_product.id


@responses.activate
def test_la_recherche_elargie_exige_deux_caracteres(auth_client):
    response = auth_client.get(EXTERNAL_SEARCH_URL, {"q": "n"})

    assert response.status_code == 200
    assert response.data["results"] == []
    assert len(responses.calls) == 0


@responses.activate
def test_un_candidat_au_code_inexploitable_est_ecarte(auth_client):
    """Proposer un résultat dont le clic échouerait serait une impasse."""
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={
            "hits": [
                {"code": "3017620422003", "product_name": "Nutella", "brands": ["Ferrero"]},
                {"code": "12", "product_name": "Code trop court", "brands": []},
                {"code": "pas-un-code", "product_name": "Code non numérique", "brands": []},
            ]
        },
        status=200,
    )

    response = auth_client.get(EXTERNAL_SEARCH_URL, {"q": "nutella"})

    assert [item["code"] for item in response.data["results"]] == ["3017620422003"]


@responses.activate
def test_une_panne_de_recherche_repond_503(auth_client):
    responses.add(responses.GET, SEARCH_URL, status=503)

    response = auth_client.get(EXTERNAL_SEARCH_URL, {"q": "nutella"})

    assert response.status_code == 503
    assert response.data["code"] == "external_source_unavailable"
