"""Regroupement des articles (spec 01 §16).

« 150 g poulet + 300 g poulet = 450 g poulet » se lit comme une addition. Ce
n'en est pas une : les quantités portent des unités, et 150 g + 1 kg valent
1150 g, pas 151. C'est la seule erreur de cette étape qui ne se voit qu'au
supermarché.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodPortion, FoodSource, UnitType
from planning.models import ItemSource, ShoppingList
from planning.services import shopping
from recipes.models import Recipe, RecipeIngredient

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 26)


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"))
    return food


@pytest.fixture
def milk(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="2",
        name="Lait",
        reference_amount=100,
        reference_unit=UnitType.MILLILITER,
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("50"))
    return food


@pytest.fixture
def basket(active_user) -> ShoppingList:
    return ShoppingList.objects.create(owner=active_user, name="Courses")


def line(food, quantity, unit, source=ItemSource.RECIPE, name=None) -> shopping.Line:
    return shopping.Line(
        name=name or (food.name if food else "Sel"),
        food=food,
        quantity=Decimal(quantity) if quantity is not None else None,
        unit_label=unit,
        source_type=source,
    )


def contents(basket: ShoppingList) -> list[tuple[str, str, str]]:
    """Articles sous une forme lisible : nom, quantité, unité."""
    return [
        (item.name, str(item.quantity), item.unit_label)
        for item in basket.items.order_by("sort_order", "id")
    ]


# --- Regroupement ------------------------------------------------------------


def test_deux_quantites_de_meme_unite_fusionnent(basket, chicken):
    shopping.add_lines(basket, [line(chicken, "150", "g"), line(chicken, "300", "g")])

    assert contents(basket) == [("Poulet", "450.000", "g")]


def test_les_unites_sont_converties_avant_dadditionner(basket, chicken):
    """150 g + 1 kg valent 1150 g. Une addition brute afficherait 151."""
    shopping.add_lines(basket, [line(chicken, "150", "g"), line(chicken, "1", "kg")])

    assert contents(basket) == [("Poulet", "1150.000", "g")]


def test_une_portion_est_convertie_avant_dadditionner(basket, chicken):
    FoodPortion.objects.create(food=chicken, name="blanc", gram_equivalent=Decimal("150"))

    shopping.add_lines(basket, [line(chicken, "100", "g"), line(chicken, "2", "blanc")])

    assert contents(basket) == [("Poulet", "400.000", "g")]


def test_des_millilitres_et_des_grammes_ne_fusionnent_pas(basket, chicken, milk):
    """Jamais de conversion volume vers masse sans densité (spec 01 §9)."""
    shopping.add_lines(basket, [line(chicken, "150", "g"), line(milk, "200", "ml")])

    assert contents(basket) == [("Poulet", "150.000", "g"), ("Lait", "200.000", "ml")]


def test_une_unite_incalculable_laisse_la_ligne_isolee(basket, chicken):
    """Une cuillère sur un aliment en grammes inventerait une densité."""
    shopping.add_lines(basket, [line(chicken, "150", "g"), line(chicken, "2", "cuillère à soupe")])

    assert contents(basket) == [
        ("Poulet", "150.000", "g"),
        ("Poulet", "2.000", "cuillère à soupe"),
    ]


def test_deux_aliments_differents_ne_fusionnent_jamais(basket, chicken):
    # Même nom, autre fiche : un aliment `user` exigerait un propriétaire.
    other = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="99", name="Poulet", reference_amount=100
    )

    shopping.add_lines(basket, [line(chicken, "150", "g"), line(other, "150", "g")])

    # Même nom, aliments distincts : deux lignes.
    assert len(contents(basket)) == 2


def test_un_article_sans_aliment_reste_isole(basket):
    shopping.add_lines(
        basket, [line(None, None, None, name="Sel"), line(None, None, None, name="Sel")]
    )

    assert contents(basket) == [("Sel", "None", None), ("Sel", "None", None)]


def test_un_article_manuel_nabsorbe_pas_une_quantite_generee(basket, chicken):
    """Son auteur l'a écrit tel quel ; le fondre le ferait disparaître."""
    shopping.add_lines(basket, [line(chicken, "150", "g", source=ItemSource.MANUAL)])

    shopping.add_lines(basket, [line(chicken, "300", "g")])

    assert contents(basket) == [("Poulet", "150.000", "g"), ("Poulet", "300.000", "g")]


def test_une_seconde_generation_fusionne_avec_lexistant(basket, chicken):
    shopping.add_lines(basket, [line(chicken, "150", "g")])

    shopping.add_lines(basket, [line(chicken, "300", "g")])

    assert contents(basket) == [("Poulet", "450.000", "g")]


# --- Sources -----------------------------------------------------------------


def test_les_lignes_dune_recette_sont_ses_ingredients(active_user, chicken):
    recipe = Recipe.objects.create(owner=active_user, name="Plat", servings=Decimal("4"))
    RecipeIngredient.objects.create(
        recipe=recipe, food=chicken, food_name="Poulet", quantity=Decimal("800"), unit_label="g"
    )

    lines = shopping.lines_from_recipes(active_user, [recipe.id])

    assert [(row.name, str(row.quantity), row.unit_label) for row in lines] == [
        ("Poulet", "800.000", "g")
    ]


def test_la_recette_dun_autre_napporte_rien(active_user, chicken, other_user):
    foreign = Recipe.objects.create(owner=other_user, name="Privée", servings=Decimal("1"))
    RecipeIngredient.objects.create(
        recipe=foreign, food=chicken, food_name="Poulet", quantity=Decimal("100"), unit_label="g"
    )

    assert shopping.lines_from_recipes(active_user, [foreign.id]) == []


def test_une_journee_apporte_ses_aliments(active_user, chicken):
    entries_service.create_food_entry(
        user=active_user,
        food=chicken,
        day=TODAY,
        meal_type=meal_types_for(active_user).first(),
        quantity=Decimal("200"),
        unit_label="g",
        consumed_at=timezone.now(),
    )

    lines = shopping.lines_from_days(active_user, [TODAY])

    assert [(row.name, str(row.quantity)) for row in lines] == [("Poulet", "200.000")]


def test_une_recette_journalisee_apporte_ses_ingredients_a_lechelle(active_user, chicken):
    """On n'achète pas des portions de blanquette."""
    recipe = Recipe.objects.create(owner=active_user, name="Plat", servings=Decimal("4"))
    RecipeIngredient.objects.create(
        recipe=recipe, food=chicken, food_name="Poulet", quantity=Decimal("800"), unit_label="g"
    )
    entries_service.create_recipe_entry(
        user=active_user,
        recipe=recipe,
        day=TODAY,
        meal_type=meal_types_for(active_user).first(),
        servings=Decimal("2"),
        consumed_at=timezone.now(),
    )

    lines = shopping.lines_from_days(active_user, [TODAY])

    # Deux portions sur quatre : la moitié des ingrédients. On compare la
    # valeur, pas sa représentation : la mise à l'échelle change la précision.
    assert [(row.name, row.quantity) for row in lines] == [("Poulet", Decimal("400"))]


def test_un_ajout_rapide_napporte_rien(active_user):
    entries_service.create_quick_add_entry(
        user=active_user,
        day=TODAY,
        meal_type=meal_types_for(active_user).first(),
        consumed_at=timezone.now(),
        values={"name": "Restaurant", "energy_kcal": Decimal("500")},
    )

    assert shopping.lines_from_days(active_user, [TODAY]) == []
