"""Duplication et ajout au journal (spec 01 §13, §14 et §18)."""

from datetime import date as date_type

from django.db import transaction

from accounts.models import User
from diary.models import MealType
from diary.services.entries import create_food_entry, create_recipe_entry
from recipes.models import ItemType, Recipe, RecipeIngredient, SavedMeal, SavedMealItem
from recipes.services import nutrition as nutrition_service

COPY_SUFFIX = " (copie)"


@transaction.atomic
def duplicate_recipe(*, user: User, recipe: Recipe) -> Recipe:
    """Copie indépendante d'une recette (spec 01 §18).

    La copie appartient à celui qui la demande et repart en privé : hériter de
    la visibilité de l'original rendrait publique, sans le dire, une recette
    qu'on vient seulement de reprendre pour soi.
    """
    copy = Recipe.objects.create(
        owner=user,
        name=f"{recipe.name}{COPY_SUFFIX}",
        description=recipe.description,
        instructions=recipe.instructions,
        servings=recipe.servings,
    )

    RecipeIngredient.objects.bulk_create(
        [
            RecipeIngredient(
                recipe=copy,
                food=ingredient.food,
                food_name=ingredient.food_name,
                quantity=ingredient.quantity,
                unit_label=ingredient.unit_label,
                sort_order=ingredient.sort_order,
            )
            for ingredient in recipe.ingredients.all()
        ]
    )

    nutrition_service.refresh(copy)
    return copy


@transaction.atomic
def duplicate_saved_meal(*, user: User, saved_meal: SavedMeal) -> SavedMeal:
    """Copie indépendante d'un repas enregistré."""
    copy = SavedMeal.objects.create(
        owner=user,
        name=f"{saved_meal.name}{COPY_SUFFIX}",
        description=saved_meal.description,
    )

    SavedMealItem.objects.bulk_create(
        [
            SavedMealItem(
                saved_meal=copy,
                item_type=item.item_type,
                food=item.food,
                recipe=item.recipe,
                item_name=item.item_name,
                quantity=item.quantity,
                unit_label=item.unit_label,
                sort_order=item.sort_order,
            )
            for item in saved_meal.items.all()
        ]
    )

    return copy


@transaction.atomic
def add_saved_meal_to_diary(
    *,
    user: User,
    saved_meal: SavedMeal,
    day: date_type,
    meal_type: MealType,
    consumed_at,
) -> tuple[list, list[str]]:
    """Déplie un repas enregistré en entrées normales et indépendantes.

    Chaque élément devient une entrée snapshotée pour elle-même : plus rien ne
    les relie ensuite, et modifier le repas enregistré ne touche pas ce qui a
    déjà été journalisé (spec 01 §13).

    Un élément dont la source a disparu est **ignoré et signalé**, plutôt que
    de faire échouer l'ajout des autres — même arbitrage que la copie d'une
    journée entière.
    """
    entries = []
    skipped: list[str] = []

    for item in saved_meal.items.select_related("food__nutrition", "recipe").prefetch_related(
        "food__portions"
    ):
        if item.item_type == ItemType.FOOD and item.food is not None:
            entries.append(
                create_food_entry(
                    user=user,
                    food=item.food,
                    day=day,
                    meal_type=meal_type,
                    quantity=item.quantity,
                    unit_label=item.unit_label,
                    consumed_at=consumed_at,
                )
            )
        elif item.item_type == ItemType.RECIPE and item.recipe is not None:
            entries.append(
                create_recipe_entry(
                    user=user,
                    recipe=item.recipe,
                    day=day,
                    meal_type=meal_type,
                    servings=item.quantity,
                    consumed_at=consumed_at,
                )
            )
        else:
            skipped.append(item.item_name)

    return entries, skipped
