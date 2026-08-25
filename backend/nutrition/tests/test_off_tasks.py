"""Rafraîchissement asynchrone du cache Open Food Facts (spec 11 §3)."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
import responses
from django.conf import settings
from django.utils import timezone

from nutrition.models import Food, FoodNutrition, FoodSource
from nutrition.tasks import is_stale, refresh_off_product, schedule_refresh

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "off"
BARCODE = "3017620422003"
PRODUCT_URL = f"{settings.OFF_PRODUCT_URL}/api/v3/product/{BARCODE}.json"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def stale_food(db) -> Food:
    """Fiche rapatriée il y a plus longtemps que le TTL."""
    food = Food.objects.create(
        source=FoodSource.OFF,
        external_id=BARCODE,
        barcode=BARCODE,
        name="Nutella (ancien nom)",
        cache_refreshed_at=timezone.now() - timedelta(days=settings.OFF_CACHE_TTL_DAYS + 1),
    )
    FoodNutrition.objects.create(food=food, energy_kcal="1")
    return food


# --- Détection de péremption -------------------------------------------------


def test_une_fiche_jamais_rafraichie_est_perimee(db):
    food = Food.objects.create(source=FoodSource.OFF, external_id="1", name="Essai")

    assert is_stale(food) is True


def test_une_fiche_recente_n_est_pas_perimee(db):
    food = Food.objects.create(
        source=FoodSource.OFF, external_id="1", name="Essai", cache_refreshed_at=timezone.now()
    )

    assert is_stale(food) is False


def test_une_fiche_ciqual_n_est_jamais_rafraichie(db):
    """Ciqual s'importe par commande, pas par appel réseau."""
    food = Food.objects.create(source=FoodSource.CIQUAL, external_id="1", name="Poulet")

    assert is_stale(food) is False


# --- Planification -----------------------------------------------------------


@responses.activate
def test_une_fiche_perimee_est_rafraichie(stale_food):
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)

    assert schedule_refresh(stale_food) is True

    stale_food.refresh_from_db()
    assert stale_food.name == "Nutella"
    assert stale_food.nutrition.energy_kcal is not None


@responses.activate
def test_une_consultation_en_rafale_ne_declenche_qu_un_appel(stale_food):
    """Le verrou évite d'empiler les tâches sur la même fiche."""
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)

    first = schedule_refresh(stale_food)
    second = schedule_refresh(stale_food)

    assert (first, second) == (True, False)
    assert len(responses.calls) == 1


@responses.activate
def test_la_source_desactivee_ne_planifie_rien(stale_food, settings):
    settings.OFF_ENABLED = False

    assert schedule_refresh(stale_food) is False
    assert len(responses.calls) == 0


# --- Résilience de la tâche --------------------------------------------------


@responses.activate
def test_une_panne_laisse_la_fiche_en_cache_intacte(stale_food):
    """La donnée périmée vaut mieux que pas de donnée du tout."""
    responses.add(responses.GET, PRODUCT_URL, status=503)

    refresh_off_product(stale_food.pk)

    stale_food.refresh_from_db()
    assert stale_food.name == "Nutella (ancien nom)"


@responses.activate
def test_un_produit_disparu_de_la_source_est_conserve(stale_food):
    """Des entrées de journal peuvent s'y référer : on ne supprime jamais."""
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_not_found.json"), status=404)
    previous = stale_food.cache_refreshed_at

    refresh_off_product(stale_food.pk)

    stale_food.refresh_from_db()
    assert stale_food.name == "Nutella (ancien nom)"
    # La date est repoussée pour ne pas réessayer à chaque consultation.
    assert stale_food.cache_refreshed_at > previous


def test_une_fiche_supprimee_entre_temps_ne_fait_pas_echouer_la_tache(db):
    refresh_off_product(999999)
