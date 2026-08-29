"""Génération d'une journée de plan (spec 01 §15, spec 07 §7).

Le premier bloc protège la règle de l'étape : **la tolérance se mesure sur les
fiches de la base, jamais sur ce que le modèle annonce**. Le schéma ne lui
demande aucun chiffre nutritionnel ; ces tests vérifient que les totaux
proviennent bien des aliments retrouvés.
"""

from datetime import date
from decimal import Decimal

import pytest

from ai.schemas import MealPlanResultSerializer, validate_ai_output
from ai.services.ai_service import AIService
from ai.services.meal_plan import (
    MAX_ATTEMPTS,
    deviations_from,
    generate_day,
    resolve_day,
    within_tolerance,
)
from nutrition.models import Food, FoodNutrition, FoodSource

pytestmark = pytest.mark.django_db

DAY = date(2026, 8, 29)
MEALS = ["Petit-déjeuner", "Déjeuner", "Dîner"]

#: Objectifs de la journée, tels que `resolve_for_date` les rend.
TARGETS = {
    "daily_calories": Decimal("2000"),
    "protein_g": Decimal("100"),
    "carbs_g": Decimal("200"),
    "fat_g": Decimal("70"),
}


@pytest.fixture
def rice(db) -> Food:
    """100 kcal aux 100 g : 1 kg pour atteindre la cible."""
    food = Food.objects.create(source=FoodSource.CIQUAL, external_id="r1", name="Riz blanc cuit")
    FoodNutrition.objects.create(
        food=food,
        energy_kcal=Decimal("100"),
        protein_g=Decimal("5"),
        carbohydrates_g=Decimal("10"),
        fat_g=Decimal("3.5"),
    )
    return food


def plan_payload(quantity, *, label="riz", unit="g", recipes=None) -> dict:
    return {
        "days": [
            {
                "date": DAY.isoformat(),
                "meals": [
                    {
                        "meal": MEALS[0],
                        "items": [
                            {"type": "food", "label": label, "quantity": quantity, "unit": unit}
                        ],
                    }
                ],
            }
        ],
        "recipes": recipes or [],
    }


def resolved(payload: dict):
    validated = validate_ai_output(MealPlanResultSerializer, payload)
    return validated, {r["name"].casefold(): r for r in validated["recipes"]}


class TestToleranceMeasuredOnTheDatabase:
    """Le modèle propose des quantités ; la base dit ce qu'elles valent."""

    def test_les_totaux_viennent_des_fiches(self, active_user, rice):
        validated, proposed = resolved(plan_payload(2000))

        day = resolve_day(active_user, validated["days"][0], proposed)

        # 2000 g de riz à 100 kcal / 100 g : 2000 kcal, pas ce qu'un modèle
        # aurait pu annoncer.
        assert day.totals["energy_kcal"] == Decimal("2000")

    def test_deux_aliments_differents_ne_donnent_pas_le_meme_ecart(self, active_user, rice):
        gras = Food.objects.create(source=FoodSource.CIQUAL, external_id="h1", name="Huile d'olive")
        FoodNutrition.objects.create(food=gras, energy_kcal=Decimal("900"))

        maigre, _ = resolved(plan_payload(2000))
        riche, _ = resolved(plan_payload(2000, label="huile"))

        ecart_maigre = deviations_from(
            resolve_day(active_user, maigre["days"][0], {}).totals, TARGETS
        )
        ecart_riche = deviations_from(
            resolve_day(active_user, riche["days"][0], {}).totals, TARGETS
        )

        assert ecart_maigre["daily_calories"] == pytest.approx(0, abs=0.5)
        assert ecart_riche["daily_calories"] > 500

    def test_un_libelle_introuvable_est_nomme_et_ecarte(self, active_user, rice):
        validated, proposed = resolved(plan_payload(200, label="zorglub"))

        day = resolve_day(active_user, validated["days"][0], proposed)

        assert day.items == []
        assert day.unmatched == ["zorglub"]

    def test_le_schema_ne_demande_aucune_valeur_nutritionnelle(self):
        from ai.schemas import meal_plan_json_schema

        item = meal_plan_json_schema(meal_names=MEALS, dates=[DAY.isoformat()])
        propriétés = item["properties"]["days"]["items"]["properties"]["meals"]["items"][
            "properties"
        ]["items"]["items"]["properties"]

        assert set(propriétés) == {"type", "label", "quantity", "unit"}


class TestTolerances:
    @pytest.mark.parametrize(
        ("ecarts", "attendu"),
        [
            pytest.param({"daily_calories": 4.9}, True, id="calories-juste-dedans"),
            pytest.param({"daily_calories": 5.0}, True, id="calories-a-la-borne"),
            pytest.param({"daily_calories": 5.1}, False, id="calories-juste-dehors"),
            pytest.param({"protein_g": 10.0}, True, id="macro-a-la-borne"),
            pytest.param({"protein_g": 10.1}, False, id="macro-juste-dehors"),
            pytest.param({"daily_calories": -5.1}, False, id="ecart-negatif"),
            pytest.param({}, True, id="rien-a-mesurer"),
        ],
    )
    def test_les_bornes_de_la_spec(self, ecarts, attendu):
        assert within_tolerance(ecarts) is attendu

    def test_un_objectif_absent_n_a_pas_d_ecart(self):
        assert deviations_from({"energy_kcal": Decimal("2000")}, {"daily_calories": None}) == {}

    def test_un_objectif_nul_est_ignore(self):
        """Diviser par zéro n'apprendrait rien."""
        assert deviations_from({"energy_kcal": Decimal("100")}, {"daily_calories": 0}) == {}


class SequenceProvider:
    """Fournisseur rendant une réponse différente à chaque appel."""

    name = "sequence"

    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.prompts: list[str] = []

    def structured_completion(self, *, prompt, **kwargs) -> dict:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self.payloads) - 1)
        return self.payloads[index]


def compose(provider, user, targets=None):
    return generate_day(
        service=AIService(provider=provider),
        user=user,
        day=DAY,
        targets=targets or TARGETS,
        meal_names=MEALS,
        constraints={},
        materials={},
        already_planned=[],
    )


class TestCorrectionLoop:
    def test_une_journee_dans_les_tolerances_sort_au_premier_essai(self, active_user, rice):
        provider = SequenceProvider([plan_payload(2000)])

        day = compose(provider, active_user)

        assert day.within_tolerance
        assert day.attempts == 1
        assert len(provider.prompts) == 1

    def test_une_journee_hors_tolerance_est_redemandee(self, active_user, rice):
        provider = SequenceProvider([plan_payload(500), plan_payload(2000)])

        day = compose(provider, active_user)

        assert day.within_tolerance
        assert day.attempts == 2
        assert len(provider.prompts) == 2

    def test_l_ecart_renvoye_au_modele_est_celui_mesure(self, active_user, rice):
        """L'écart annoncé est celui qui reste **après ajustement**.

        Lui reprocher un écart que le dosage a déjà corrigé le ferait travailler
        sur un problème résolu.
        """
        # 500 g de riz, portés à 1250 g par l'ajustement (facteur maximal) :
        # 1250 kcal contre 2000 visées, soit -37,5 %.
        provider = SequenceProvider([plan_payload(500), plan_payload(2000)])

        compose(provider, active_user)

        assert "-38 %" in provider.prompts[1]
        # Et il reçoit ce que ses quantités valaient réellement.
        assert "kcal" in provider.prompts[1]

    def test_trois_essais_au_maximum(self, active_user, rice):
        """Sans plafond dur, une journée impossible appellerait indéfiniment."""
        provider = SequenceProvider([plan_payload(500)])

        day = compose(provider, active_user)

        assert not day.within_tolerance
        assert day.attempts == MAX_ATTEMPTS
        assert len(provider.prompts) == MAX_ATTEMPTS

    def test_la_meilleure_tentative_est_rendue(self, active_user, rice):
        """La moins mauvaise sort, pas la dernière.

        Aucune de ces compositions n'atteint la cible même au facteur maximal :
        300 g donnent 750 kcal, 700 g en donnent 1750, 100 g en donnent 250.
        """
        provider = SequenceProvider([plan_payload(300), plan_payload(700), plan_payload(100)])

        day = compose(provider, active_user)

        assert not day.within_tolerance
        assert day.totals["energy_kcal"] == Decimal("1750")
