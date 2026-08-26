"""Unités de saisie et conversion (spec 01 §9).

La règle décisive : jamais de conversion millilitres ↔ grammes sans densité
connue. Une unité non calculable doit être refusée, jamais approximée.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from nutrition.models import Food, FoodPortion, FoodSource, UnitType
from nutrition.services.quantities import (
    TABLESPOON,
    TEASPOON,
    available_units,
    resolve_multiplier,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def solid(db) -> Food:
    return Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="1",
        name="Poulet rôti",
        reference_amount=100,
        reference_unit=UnitType.GRAM,
    )


@pytest.fixture
def liquid(db) -> Food:
    return Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="2",
        name="Huile d’olive",
        reference_amount=100,
        reference_unit=UnitType.MILLILITER,
    )


@pytest.fixture
def countable(db) -> Food:
    return Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="3",
        name="Œuf",
        reference_amount=1,
        reference_unit=UnitType.UNIT,
    )


# --- Unités proposées --------------------------------------------------------


def test_un_aliment_en_grammes_ne_propose_pas_les_cuilleres(solid):
    """Une cuillère est une mesure de volume : l'accepter inventerait une densité."""
    units = available_units(solid)

    assert units == ["g", "kg"]
    assert TABLESPOON not in units


def test_un_aliment_en_millilitres_propose_les_cuilleres(liquid):
    assert available_units(liquid) == ["ml", "cl", TEASPOON, TABLESPOON]


def test_un_aliment_a_l_unite_ne_propose_que_l_unite(countable):
    assert available_units(countable) == ["unité"]


def test_une_portion_compatible_s_ajoute_aux_unites(solid):
    FoodPortion.objects.create(food=solid, name="1 blanc", gram_equivalent=Decimal("180"))

    assert "1 blanc" in available_units(solid)


def test_une_portion_incompatible_n_est_pas_proposee(solid):
    """Une portion en millilitres ne dit rien d'un aliment mesuré en grammes."""
    FoodPortion.objects.create(food=solid, name="1 verre", milliliter_equivalent=Decimal("200"))

    assert "1 verre" not in available_units(solid)


# --- Conversion --------------------------------------------------------------


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        (Decimal("150"), "g", Decimal("1.5")),
        (Decimal("100"), "g", Decimal("1")),
        (Decimal("0.25"), "kg", Decimal("2.5")),
    ],
)
def test_conversion_des_masses(solid, quantity, unit, expected):
    assert resolve_multiplier(solid, quantity, unit) == expected


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        (Decimal("50"), "ml", Decimal("0.5")),
        (Decimal("5"), "cl", Decimal("0.5")),
        (Decimal("1"), TABLESPOON, Decimal("0.15")),
        (Decimal("2"), TEASPOON, Decimal("0.1")),
    ],
)
def test_conversion_des_volumes(liquid, quantity, unit, expected):
    assert resolve_multiplier(liquid, quantity, unit) == expected


def test_conversion_par_portion(solid):
    FoodPortion.objects.create(food=solid, name="1 blanc", gram_equivalent=Decimal("180"))

    assert resolve_multiplier(solid, Decimal("2"), "1 blanc") == Decimal("3.6")


# --- Refus -------------------------------------------------------------------


def test_une_cuillere_sur_un_solide_est_refusee(solid):
    """Le message doit orienter, pas seulement constater l'échec."""
    with pytest.raises(ValidationError) as error:
        resolve_multiplier(solid, Decimal("1"), TABLESPOON)

    assert "unit_label" in error.value.message_dict


def test_les_millilitres_sur_un_solide_sont_refuses(solid):
    with pytest.raises(ValidationError):
        resolve_multiplier(solid, Decimal("100"), "ml")


def test_les_grammes_sur_un_liquide_sont_refuses(liquid):
    with pytest.raises(ValidationError):
        resolve_multiplier(liquid, Decimal("100"), "g")


def test_une_portion_sans_equivalent_utilisable_est_refusee(solid):
    FoodPortion.objects.create(food=solid, name="1 verre", milliliter_equivalent=Decimal("200"))

    with pytest.raises(ValidationError):
        resolve_multiplier(solid, Decimal("1"), "1 verre")


def test_une_unite_inconnue_est_refusee(solid):
    with pytest.raises(ValidationError):
        resolve_multiplier(solid, Decimal("1"), "poignée")
