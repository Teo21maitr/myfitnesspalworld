"""Enregistrement d'un plan, et ce qu'on en tire (spec 01 §15).

Deux règles gouvernent ce fichier :

* **l'ajout au journal n'écrase jamais** — un repas déjà rempli est nommé et
  attend confirmation ;
* **une recette inventée n'est enregistrée qu'à l'acceptation du plan**, et
  jamais incomplète.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from diary.models import DiaryEntry
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from planning.models import PlanEntryType
from planning.services import plans, shopping
from recipes.models import Recipe, RecipeIngredient

pytestmark = pytest.mark.django_db

MONDAY = date(2026, 8, 31)
NOON = timezone.make_aware(datetime(2026, 8, 31, 12, 0))


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="p1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"), protein_g=Decimal("25"))
    return food


@pytest.fixture
def rice(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="r1", name="Riz", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("130"))
    return food


@pytest.fixture
def meals(active_user):
    return {meal.system_key: meal for meal in meal_types_for(active_user)}


def payload(entries: list[dict], *, days: int = 1) -> dict:
    return {
        "name": "Semaine test",
        "notes": "",
        "generated_by_ai": True,
        "days": [
            {"date": MONDAY + timedelta(days=offset), "entries": entries} for offset in range(days)
        ],
    }


def food_entry(meal, food, quantity="150") -> dict:
    return {
        "meal_type_id": meal.pk,
        "entry_type": PlanEntryType.FOOD,
        "food_id": food.pk,
        "quantity": Decimal(quantity),
        "unit_label": "g",
        "generated_by_ai": True,
    }


class TestPersistence:
    def test_un_plan_est_enregistre_avec_ses_journees(self, active_user, meals, chicken):
        plan, skipped = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)], days=3)
        )

        assert plan.days.count() == 3
        assert plan.start_date == MONDAY
        assert plan.end_date == MONDAY + timedelta(days=2)
        assert skipped == []

    def test_un_aliment_invisible_est_ignore(self, active_user, other_user, meals):
        from nutrition.models import FoodVisibility

        prive = Food.objects.create(
            source=FoodSource.USER,
            owner=other_user,
            name="Secret",
            visibility=FoodVisibility.PRIVATE,
        )
        FoodNutrition.objects.create(food=prive, energy_kcal=Decimal("100"))

        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], prive)])
        )

        assert plan.days.first().entries.count() == 0


class TestInventedRecipes:
    def recipe_entry(self, meal, chicken, rice) -> dict:
        return {
            "meal_type_id": meal.pk,
            "entry_type": PlanEntryType.RECIPE,
            "new_recipe": {
                "name": "Poulet au riz",
                "servings": Decimal("2"),
                "instructions": "Tout mélanger.",
                "ingredients": [
                    {"food_id": chicken.pk, "quantity": Decimal("300"), "unit_label": "g"},
                    {"food_id": rice.pk, "quantity": Decimal("200"), "unit_label": "g"},
                ],
            },
            "quantity": Decimal("1"),
            "unit_label": "portion",
            "generated_by_ai": True,
        }

    def test_une_recette_inventee_devient_une_vraie_recette(
        self, active_user, meals, chicken, rice
    ):
        plans.create_plan(
            user=active_user,
            payload=payload([self.recipe_entry(meals["dinner"], chicken, rice)]),
        )

        recipe = Recipe.objects.get(owner=active_user, name="Poulet au riz")
        assert recipe.ingredients.count() == 2
        # La nutrition est calculée par le backend, pas fournie par le modèle.
        # 300 g de poulet à 200 kcal + 200 g de riz à 130, pour 2 portions.
        assert recipe.nutrition.energy_kcal == Decimal("430.000")

    def test_la_meme_recette_n_est_creee_qu_une_fois(self, active_user, meals, chicken, rice):
        entry = self.recipe_entry(meals["dinner"], chicken, rice)
        plans.create_plan(user=active_user, payload=payload([entry, dict(entry)], days=2))

        assert Recipe.objects.filter(owner=active_user, name="Poulet au riz").count() == 1

    def test_une_recette_sans_ingredient_retrouvable_est_ecartee_et_nommee(
        self, active_user, meals
    ):
        entry = {
            "meal_type_id": meals["dinner"].pk,
            "entry_type": PlanEntryType.RECIPE,
            "new_recipe": {
                "name": "Plat fantôme",
                "servings": Decimal("2"),
                "instructions": "",
                "ingredients": [{"food_id": 999999, "quantity": Decimal("1"), "unit_label": "g"}],
            },
            "quantity": Decimal("1"),
            "unit_label": "portion",
        }

        plan, skipped = plans.create_plan(user=active_user, payload=payload([entry]))

        assert skipped == ["Plat fantôme"]
        assert not Recipe.objects.filter(name="Plat fantôme").exists()
        assert plan.days.first().entries.count() == 0


class TestAddToDiary:
    def test_le_plan_se_deplie_en_entrees_independantes(self, active_user, meals, chicken):
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)])
        )

        entries, skipped = plans.add_plan_to_diary(user=active_user, plan=plan)

        assert len(entries) == 1
        assert skipped == []
        # Snapshotée pour elle-même : le plan ne la tient plus.
        assert entries[0].snapshot_name == "Poulet"
        assert entries[0].snapshot_energy_kcal == Decimal("200.000")

    def test_rien_n_est_remplace(self, active_user, meals, chicken, rice):
        """Le plan s'ajoute par-dessus ce que la journée contenait déjà."""
        existante = entries_service.create_food_entry(
            user=active_user,
            food=rice,
            day=MONDAY,
            meal_type=meals["lunch"],
            quantity=Decimal("100"),
            unit_label="g",
            consumed_at=NOON,
        )
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)])
        )

        plans.add_plan_to_diary(user=active_user, plan=plan)

        assert DiaryEntry.objects.filter(pk=existante.pk).exists()
        assert DiaryEntry.objects.count() == 2

    def test_un_repas_deja_rempli_est_nomme(self, active_user, meals, chicken, rice):
        entries_service.create_food_entry(
            user=active_user,
            food=rice,
            day=MONDAY,
            meal_type=meals["lunch"],
            quantity=Decimal("100"),
            unit_label="g",
            consumed_at=NOON,
        )
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)])
        )

        assert plans.filled_meals(active_user, plan) == ["31/08 — Déjeuner"]

    def test_un_repas_vide_n_est_pas_signale(self, active_user, meals, chicken):
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)])
        )

        assert plans.filled_meals(active_user, plan) == []

    def test_un_element_sans_source_est_ignore_et_nomme(self, active_user, meals, chicken):
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)])
        )
        chicken.delete()

        entries, skipped = plans.add_plan_to_diary(user=active_user, plan=plan)

        assert entries == []
        assert skipped == ["31/08 — Déjeuner"]


class TestShoppingLines:
    def test_un_aliment_planifie_verse_sa_quantite(self, active_user, meals, chicken):
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken, "250")])
        )

        lines = shopping.lines_from_meal_plan(active_user, plan.pk)

        assert len(lines) == 1
        assert lines[0].quantity == Decimal("250")

    def test_une_recette_verse_ses_ingredients_a_l_echelle(self, active_user, meals, chicken, rice):
        """On n'achète pas des portions de blanquette."""
        recipe = Recipe.objects.create(owner=active_user, name="Plat", servings=Decimal("4"))
        RecipeIngredient.objects.create(
            recipe=recipe, food=chicken, quantity=Decimal("800"), unit_label="g"
        )
        plan, _ = plans.create_plan(
            user=active_user,
            payload=payload(
                [
                    {
                        "meal_type_id": meals["dinner"].pk,
                        "entry_type": PlanEntryType.RECIPE,
                        "recipe_id": recipe.pk,
                        "quantity": Decimal("2"),
                        "unit_label": "portion",
                    }
                ]
            ),
        )

        lines = shopping.lines_from_meal_plan(active_user, plan.pk)

        # Deux portions sur quatre : la moitié des 800 g.
        assert lines[0].quantity == Decimal("400")

    def test_le_plan_d_un_autre_ne_verse_rien(self, active_user, other_user, meals, chicken):
        plan, _ = plans.create_plan(
            user=active_user, payload=payload([food_entry(meals["lunch"], chicken)])
        )

        assert shopping.lines_from_meal_plan(other_user, plan.pk) == []
