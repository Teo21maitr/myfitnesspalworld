"""Conversion des produits Open Food Facts (spec 11 §3).

Les charges utiles de `fixtures/off/` ont été capturées sur l'API réelle. Un
JSON inventé ne reproduirait ni la notation scientifique, ni les flottants
bruités, ni les unités effectivement employées — c'est-à-dire précisément ce
qui casse.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from nutrition.models import Food, FoodSource, UnitType
from nutrition.services.off import (
    NUTRIENT_MAP,
    NutrientMapping,
    UnusableProduct,
    read_brand,
    read_external_updated_at,
    read_name,
    read_nutrient,
    read_nutrition,
    upsert_product,
)

FIXTURES = Path(__file__).parent / "fixtures" / "off"


def load_product(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["product"]


# --- Le piège de l'énergie ---------------------------------------------------


def test_l_energie_est_lue_en_kilocalories_pas_en_kilojoules():
    """`energy_100g` est en kJ, `energy-kcal_100g` en kcal.

    Pour le Nutella, 2252 contre 539 : se tromper de clé multiplierait toutes
    les calories du journal par 4,18.
    """
    product = load_product("product_nutella.json")

    values = read_nutrition(product)

    assert values["energy_kcal"] == Decimal("539.000")
    assert product["nutriments"]["energy_100g"] == 2252  # la valeur à ne pas lire


# --- Le piège des unités -----------------------------------------------------


def test_les_micronutriments_sont_convertis_depuis_les_grammes():
    """Open Food Facts exprime tout en grammes, le modèle en mg et µg."""
    product = load_product("product_us_micronutrients.json")
    nutriments = product["nutriments"]

    values = read_nutrition(product)

    # Relevé dans la charge utile : 0,148 g de calcium, avec `calcium_unit: g`.
    assert nutriments["calcium_unit"] == "g"
    assert values["calcium_mg"] == Decimal("148.077")
    assert values["cholesterol_mg"] == Decimal("19.231")
    assert values["iron_mg"] == Decimal("4.038")


def test_les_vitamines_en_microgrammes_sont_converties():
    """3,1e-06 g de vitamine D valent 3,1 µg — la notation scientifique comprise."""
    product = load_product("product_vitamins.json")

    values = read_nutrition(product)

    assert product["nutriments"]["vitamin-d_100g"] == pytest.approx(3.1e-06)
    assert values["vitamin_d_ug"] == Decimal("3.100")


def test_le_sodium_du_nutella_correspond_a_l_etiquette():
    """0,0428 g de sodium et 0,107 g de sel : valeurs de l'emballage."""
    values = read_nutrition(load_product("product_nutella.json"))

    assert values["sodium_mg"] == Decimal("42.800")
    assert values["salt_g"] == Decimal("0.107")


# --- Valeur inconnue contre valeur nulle -------------------------------------


def test_un_nutriment_absent_reste_inconnu():
    """Absent ne veut pas dire zéro (spec 01 §8)."""
    values = read_nutrition(load_product("product_nutella.json"))

    # Le Nutella ne déclare aucune vitamine.
    assert values["vitamin_c_mg"] is None
    assert values["fiber_g"] is None
    assert Decimal(0) not in {values["vitamin_c_mg"], values["fiber_g"]}


def test_un_produit_sans_aucune_nutrition_reste_exploitable():
    """Un produit partiellement renseigné reste utilisable (spec 01 §8)."""
    values = read_nutrition({"code": "1", "product_name": "Inconnu"})

    assert set(values.values()) == {None}


def test_seules_les_valeurs_pour_100_g_sont_lues():
    """`nutrition_data_per: serving` ne doit pas faire lire les valeurs par portion."""
    product = {
        "code": "1",
        "product_name": "Barre",
        "nutrition_data_per": "serving",
        "nutriments": {"energy-kcal_serving": 250, "proteins_serving": 8},
    }

    values = read_nutrition(product)

    assert values["energy_kcal"] is None
    assert values["protein_g"] is None


# --- Robustesse aux données collaboratives -----------------------------------


@pytest.mark.parametrize(
    "raw",
    [None, "", "beaucoup", True, float("nan"), float("inf"), -3],
    ids=["absent", "vide", "texte", "booleen", "nan", "infini", "negatif"],
)
def test_une_valeur_illisible_reste_inconnue(raw):
    """Aucune saisie fantaisiste ne doit produire une valeur fausse."""
    mapping = NUTRIENT_MAP["protein_g"]

    assert read_nutrient({mapping.off_key: raw}, mapping) is None


def test_une_valeur_aberrante_est_ecartee_plutot_que_tronquee():
    """Une teneur impossible reste inconnue.

    La tronquer fabriquerait une donnée ; la laisser passer ferait échouer
    l'écriture, les champs étant plafonnés à 999 999,999.
    """
    mapping = NUTRIENT_MAP["protein_g"]

    assert read_nutrient({mapping.off_key: 4000}, mapping) is None


def test_aucune_conversion_ne_depasse_la_capacite_du_champ():
    """Les plafonds doivent rester dans ce que la base sait stocker."""
    maximum_storable = Decimal("999999.999")

    for name, mapping in NUTRIENT_MAP.items():
        assert mapping.maximum <= maximum_storable, name


def test_une_valeur_juste_sous_le_plafond_est_conservee():
    mapping = NutrientMapping("essai_100g", Decimal("1000"), Decimal("100000"))

    assert read_nutrient({"essai_100g": 99}, mapping) == Decimal("99000.000")


# --- Identité du produit -----------------------------------------------------


def test_le_nom_francais_est_prefere():
    product = {"product_name": "Chocolate spread", "product_name_fr": "Pâte à tartiner"}

    assert read_name(product) == "Pâte à tartiner"


def test_le_nom_international_sert_de_repli():
    assert read_name({"product_name": "Hazelnut Spread"}) == "Hazelnut Spread"


def test_seule_la_premiere_marque_est_retenue():
    """`brands` liste plusieurs marques ; la première est la plus significative."""
    product = load_product("product_nutella.json")

    assert product["brands"] == "Nutella, Ferrero, Yum yum"
    assert read_brand(product) == "Nutella"


def test_la_date_de_modification_est_lue():
    product = load_product("product_nutella.json")

    updated = read_external_updated_at(product)

    assert updated is not None
    assert updated.tzinfo is not None


@pytest.mark.parametrize("raw", [None, 0, -1, "hier", True])
def test_une_date_illisible_reste_inconnue(raw):
    assert read_external_updated_at({"last_modified_t": raw}) is None


# --- Enregistrement ----------------------------------------------------------


@pytest.mark.django_db
def test_le_produit_est_enregistre_comme_fiche_open_food_facts():
    food = upsert_product(load_product("product_nutella.json"))

    assert food.source == FoodSource.OFF
    assert food.external_id == "3017620422003"
    assert food.barcode == "3017620422003"
    assert food.name == "Nutella"
    assert food.reference_amount == 100
    assert food.reference_unit == UnitType.GRAM
    assert food.default_unit_type == UnitType.GRAM
    # Base collaborative : jamais présentée comme vérifiée (spec 11 §3).
    assert food.is_verified is False
    assert food.cache_refreshed_at is not None
    assert food.nutrition.energy_kcal == Decimal("539.000")


@pytest.mark.django_db
def test_reimporter_le_meme_produit_le_met_a_jour_sans_le_dupliquer():
    """L'idempotence repose sur la contrainte `(source, external_id)`."""
    product = load_product("product_nutella.json")

    first = upsert_product(product)
    second = upsert_product(product)

    assert first.pk == second.pk
    assert Food.objects.filter(source=FoodSource.OFF, external_id="3017620422003").count() == 1


@pytest.mark.django_db
def test_un_nutriment_disparu_de_la_source_redevient_inconnu():
    """Le rafraîchissement ne doit pas conserver une valeur périmée."""
    product = load_product("product_nutella.json")
    upsert_product(product)

    stripped = {**product, "nutriments": {}}
    food = upsert_product(stripped)

    assert food.nutrition.energy_kcal is None


@pytest.mark.django_db
def test_un_produit_sans_nom_est_refuse():
    """Sans nom, la fiche ne peut ni s'afficher ni se rechercher."""
    with pytest.raises(UnusableProduct):
        upsert_product({"code": "3017620422003", "nutriments": {}})


@pytest.mark.django_db
def test_un_produit_sans_code_barres_est_refuse():
    with pytest.raises(UnusableProduct):
        upsert_product({"product_name": "Sans code"})


@pytest.mark.django_db
def test_le_texte_de_recherche_est_alimente():
    """La fiche rapatriée doit être trouvable localement ensuite."""
    food = upsert_product(load_product("product_nutella.json"))

    assert "nutella" in food.search_text
