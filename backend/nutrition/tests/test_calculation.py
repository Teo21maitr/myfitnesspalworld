"""Calcul calorique déterministe (spec 01 §3).

Les fonctions testées ici sont pures : elles ne touchent ni la base ni le
réseau, ce qui permet de vérifier la formule valeur par valeur.
"""

from datetime import date
from decimal import Decimal

import pytest

from accounts.models import ActivityLevel, GoalType, SexForCalculation
from common.dates import age_on
from nutrition.services.calculation import (
    ACTIVITY_FACTORS,
    ESTIMATION_NOTICE,
    basal_metabolic_rate,
    body_mass_index,
    calorie_delta,
    collect_warnings,
    daily_calorie_target,
    estimate,
    macro_calories,
    suggest_macros,
    total_energy_expenditure,
)

# --- Métabolisme de base ------------------------------------------------------


def test_bmr_homme():
    """Mifflin-St Jeor : 10*80 + 6.25*180 - 5*30 + 5 = 1780."""
    result = basal_metabolic_rate(
        sex=SexForCalculation.MALE,
        weight_kg=Decimal("80"),
        height_cm=Decimal("180"),
        age=30,
    )

    assert result == Decimal("1780.0")


def test_bmr_femme():
    """10*65 + 6.25*165 - 5*30 - 161 = 1370.25, arrondi à la kilocalorie."""
    result = basal_metabolic_rate(
        sex=SexForCalculation.FEMALE,
        weight_kg=Decimal("65"),
        height_cm=Decimal("165"),
        age=30,
    )

    assert result == Decimal("1370")


def test_le_bmr_reste_en_decimal():
    result = basal_metabolic_rate(
        sex=SexForCalculation.MALE,
        weight_kg=Decimal("80.5"),
        height_cm=Decimal("180.5"),
        age=31,
    )

    assert isinstance(result, Decimal)


@pytest.mark.parametrize(
    ("level", "factor"),
    [
        (ActivityLevel.SEDENTARY, Decimal("1.2")),
        (ActivityLevel.LIGHTLY_ACTIVE, Decimal("1.375")),
        (ActivityLevel.MODERATELY_ACTIVE, Decimal("1.55")),
        (ActivityLevel.VERY_ACTIVE, Decimal("1.725")),
        (ActivityLevel.EXTREMELY_ACTIVE, Decimal("1.9")),
    ],
)
def test_chaque_niveau_dactivite_applique_son_coefficient(level, factor):
    bmr = Decimal("1800")

    assert total_energy_expenditure(bmr, level) == (bmr * factor).quantize(Decimal("1"))
    assert ACTIVITY_FACTORS[level] == factor


# --- Déficit et surplus -------------------------------------------------------


def test_perte_applique_un_deficit():
    assert calorie_delta(GoalType.LOSS, Decimal("0.5")) == Decimal("-550.00")


def test_prise_applique_un_surplus():
    assert calorie_delta(GoalType.GAIN, Decimal("0.25")) == Decimal("275.00")


def test_maintien_ignore_le_rythme():
    assert calorie_delta(GoalType.MAINTENANCE, Decimal("0.5")) == Decimal("0")


def test_rythme_absent_vaut_zero():
    assert calorie_delta(GoalType.LOSS, None) == Decimal("0")


def test_objectif_calorique_complet():
    target = daily_calorie_target(Decimal("2500"), GoalType.LOSS, Decimal("0.5"))

    assert target == Decimal("1950")


def test_lobjectif_calorique_ne_devient_jamais_negatif():
    target = daily_calorie_target(Decimal("1000"), GoalType.LOSS, Decimal("2"))

    assert target == Decimal("0")


# --- Macronutriments ----------------------------------------------------------


def test_repartition_des_macros_en_perte():
    """30 % protéines, 30 % lipides, 40 % glucides de 2000 kcal."""
    macros = suggest_macros(Decimal("2000"), GoalType.LOSS)

    assert macros["protein"] == Decimal("150")
    assert macros["fat"] == Decimal("67")
    assert macros["carbs"] == Decimal("200")


@pytest.mark.parametrize("goal", [GoalType.LOSS, GoalType.MAINTENANCE, GoalType.GAIN])
def test_les_macros_retombent_sur_les_calories(goal):
    calories = Decimal("2200")
    macros = suggest_macros(calories, goal)

    implied = macro_calories(macros["protein"], macros["carbs"], macros["fat"])

    # L'arrondi au gramme près introduit un écart de quelques kilocalories.
    assert abs(implied - calories) <= Decimal("10")


@pytest.mark.parametrize("goal", [GoalType.LOSS, GoalType.MAINTENANCE, GoalType.GAIN])
def test_les_macros_ne_sont_jamais_negatives(goal):
    macros = suggest_macros(Decimal("900"), goal)

    assert all(value >= 0 for value in macros.values())


# --- Âge et IMC ---------------------------------------------------------------


def test_age_revolu():
    assert age_on(date(1996, 8, 25), date(2026, 8, 24)) == 29
    assert age_on(date(1996, 8, 24), date(2026, 8, 24)) == 30


def test_imc():
    assert body_mass_index(Decimal("80"), Decimal("180")) == Decimal("24.7")


# --- Avertissements -----------------------------------------------------------


def test_avertissement_calories_trop_basses_pour_une_femme():
    warnings = collect_warnings(
        sex=SexForCalculation.FEMALE,
        daily_calories=Decimal("1100"),
        rate_kg_per_week=None,
        target_weight_kg=None,
        height_cm=Decimal("165"),
    )

    assert any("1200" in message for message in warnings)


def test_pas_davertissement_pour_des_calories_raisonnables():
    warnings = collect_warnings(
        sex=SexForCalculation.MALE,
        daily_calories=Decimal("2200"),
        rate_kg_per_week=Decimal("0.5"),
        target_weight_kg=Decimal("75"),
        height_cm=Decimal("180"),
    )

    assert warnings == []


def test_avertissement_rythme_trop_ambitieux():
    warnings = collect_warnings(
        sex=SexForCalculation.MALE,
        daily_calories=Decimal("2000"),
        rate_kg_per_week=Decimal("1.5"),
        target_weight_kg=None,
        height_cm=Decimal("180"),
    )

    assert any("rythme" in message.lower() for message in warnings)


def test_avertissement_poids_cible_trop_bas():
    warnings = collect_warnings(
        sex=SexForCalculation.FEMALE,
        daily_calories=Decimal("1800"),
        rate_kg_per_week=Decimal("0.5"),
        target_weight_kg=Decimal("45"),
        height_cm=Decimal("170"),
    )

    assert any("IMC" in message for message in warnings)


# --- Chaîne complète ----------------------------------------------------------


def test_estimation_complete():
    result = estimate(
        sex=SexForCalculation.MALE,
        weight_kg=Decimal("80"),
        height_cm=Decimal("180"),
        birth_date=date(1996, 1, 1),
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal_type=GoalType.LOSS,
        rate_kg_per_week=Decimal("0.5"),
        target_weight_kg=Decimal("75"),
        today=date(2026, 1, 1),
    )

    assert result.bmr == Decimal("1780.0")
    assert result.tdee == Decimal("2759.0")
    assert result.daily_calories == Decimal("2209")
    assert result.warnings == []
    assert result.notice == ESTIMATION_NOTICE


def test_lestimation_porte_toujours_la_mention_obligatoire():
    """Spec 01 §3 : la mention doit accompagner chaque estimation."""
    result = estimate(
        sex=SexForCalculation.FEMALE,
        weight_kg=Decimal("60"),
        height_cm=Decimal("165"),
        birth_date=date(1990, 6, 15),
        activity_level=ActivityLevel.SEDENTARY,
        goal_type=GoalType.MAINTENANCE,
        today=date(2026, 1, 1),
    )

    assert "estimation" in result.notice
    assert "recommandation médicale" in result.notice
