"""Nutrition d'une recette, par portion (spec 01 §14, spec 01 §8)."""

from decimal import Decimal

import pytest

from nutrition.models import Food, FoodNutrition, FoodPortion, FoodSource, UnitType
from recipes.models import Recipe, RecipeIngredient
from recipes.services import nutrition as nutrition_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(
        food=food, energy_kcal=Decimal("200"), protein_g=Decimal("30"), fiber_g=None
    )
    return food


@pytest.fixture
def rice(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="2", name="Riz", reference_amount=100
    )
    FoodNutrition.objects.create(
        food=food, energy_kcal=Decimal("100"), protein_g=Decimal("3"), fiber_g=Decimal("1")
    )
    return food


def make_recipe(user, servings="2") -> Recipe:
    return Recipe.objects.create(owner=user, name="Poulet riz", servings=Decimal(servings))


def add_ingredient(recipe, food, quantity="200", unit="g") -> RecipeIngredient:
    return RecipeIngredient.objects.create(
        recipe=recipe,
        food=food,
        food_name=food.name,
        quantity=Decimal(quantity),
        unit_label=unit,
    )


def test_les_ingredients_sont_sommes_puis_divises_par_les_portions(active_user, chicken, rice):
    recipe = make_recipe(active_user)
    add_ingredient(recipe, chicken, "200")  # 400 kcal
    add_ingredient(recipe, rice, "300")  # 300 kcal

    per_serving, _ = nutrition_service.compute(recipe)

    assert per_serving["energy_kcal"] == Decimal("350")
    assert per_serving["protein_g"] == Decimal("34.5")


def test_un_nutriment_inconnu_dun_seul_ingredient_rend_le_total_partiel(active_user, chicken, rice):
    """Le total additionne ce qu'on sait, et le signale (spec 01 §8)."""
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "100")  # fibres inconnues
    add_ingredient(recipe, rice, "100")  # 1 g de fibres

    per_serving, incomplete = nutrition_service.compute(recipe)

    assert per_serving["fiber_g"] == Decimal("1")
    assert "fiber_g" in incomplete


def test_un_nutriment_inconnu_de_tous_reste_nul(active_user, chicken):
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "100")

    per_serving, incomplete = nutrition_service.compute(recipe)

    # Inconnu partout : `None`, et non signalé comme partiel puisqu'aucune
    # source ne le renseigne.
    assert per_serving["fiber_g"] is None
    assert "fiber_g" not in incomplete


def test_une_recette_sans_ingredient_vaut_zero(active_user):
    """Rien dedans n'est pas une donnée manquante : c'est zéro."""
    recipe = make_recipe(active_user, servings="1")

    per_serving, _ = nutrition_service.compute(recipe)

    assert per_serving["energy_kcal"] == Decimal("0")


def test_changer_le_nombre_de_portions_change_la_valeur_par_portion(active_user, chicken):
    recipe = make_recipe(active_user, servings="2")
    add_ingredient(recipe, chicken, "200")  # 400 kcal
    assert nutrition_service.refresh(recipe).energy_kcal == Decimal("200")

    recipe.servings = Decimal("4")
    recipe.save()

    assert nutrition_service.refresh(recipe).energy_kcal == Decimal("100")


def test_un_ingredient_sans_aliment_rend_la_recette_partielle(active_user, chicken, rice):
    """L'aliment supprimé ne vaut pas zéro : il rend le total partiel."""
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "100")
    orphan = add_ingredient(recipe, rice, "100")
    orphan.food = None
    orphan.save()

    per_serving, incomplete = nutrition_service.compute(recipe)

    assert per_serving["energy_kcal"] == Decimal("200")
    assert "energy_kcal" in incomplete


def test_une_unite_devenue_incalculable_rend_lingredient_inconnu(active_user, chicken):
    """Une portion supprimée ne doit pas faire échouer la lecture de la recette."""
    portion = FoodPortion.objects.create(food=chicken, name="blanc", gram_equivalent=Decimal("150"))
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "1", unit="blanc")
    portion.delete()

    per_serving, incomplete = nutrition_service.compute(recipe)

    assert per_serving["energy_kcal"] is None
    assert "energy_kcal" not in incomplete


def test_le_cache_perime_quand_un_aliment_change(active_user, chicken):
    """Le cache peut vieillir sans que la recette bouge."""
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "100")
    assert nutrition_service.refresh(recipe).energy_kcal == Decimal("200")

    chicken.nutrition.energy_kcal = Decimal("300")
    chicken.nutrition.save()
    chicken.save()  # `updated_at` marque le changement

    assert nutrition_service.ensure_fresh(recipe).energy_kcal == Decimal("300")


def test_le_cache_intact_nest_pas_recalcule(active_user, chicken):
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "100")
    first = nutrition_service.refresh(recipe)

    second = nutrition_service.ensure_fresh(recipe)

    assert second.computed_at == first.computed_at


def test_une_unite_de_volume_est_refusee_sur_un_aliment_en_grammes(active_user, chicken):
    """Jamais de conversion ml vers g sans densité (spec 01 §9)."""
    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, chicken, "1", unit="cuillère à soupe")

    per_serving, _ = nutrition_service.compute(recipe)

    assert per_serving["energy_kcal"] is None


def test_les_millilitres_fonctionnent_sur_un_aliment_en_millilitres(active_user):
    milk = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="3",
        name="Lait",
        reference_amount=100,
        reference_unit=UnitType.MILLILITER,
    )
    FoodNutrition.objects.create(food=milk, energy_kcal=Decimal("50"))

    recipe = make_recipe(active_user, servings="1")
    add_ingredient(recipe, milk, "200", unit="ml")

    per_serving, _ = nutrition_service.compute(recipe)

    assert per_serving["energy_kcal"] == Decimal("100")
