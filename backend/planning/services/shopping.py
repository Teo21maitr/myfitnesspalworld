"""Constitution d'une liste de courses (spec 01 §16).

« Regrouper les ingrédients compatibles » se lit comme une addition. Ce n'en est
pas une : les quantités portent des unités. 150 g et 1 kg du même poulet se
regroupent bien, mais leur somme vaut 1150 g, pas 151 — un nombre plausible,
faux d'un facteur sept, et que rien à l'écran ne signale.

On convertit donc chaque quantité dans l'unité de référence de son aliment avant
d'additionner. **Et ce qui ne se convertit pas ne se regroupe pas** : la ligne
reste séparée plutôt qu'approximée (spec 01 §9).
"""

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from diary.models import EntryType
from diary.services.day import day_entries
from nutrition.models import Food
from nutrition.services.quantities import resolve_factor
from planning.models import ItemSource, MealPlanEntry, ShoppingList, ShoppingListItem
from recipes.models import Recipe


@dataclass(frozen=True)
class Line:
    """Une quantité à acheter, avant regroupement."""

    name: str
    food: Food | None
    quantity: Decimal | None
    unit_label: str | None
    source_type: str


def normalized_quantity(
    food: Food | None, quantity: Decimal | None, unit_label: str | None
) -> Decimal | None:
    """Quantité exprimée dans l'unité de référence de l'aliment.

    `None` dès qu'on ne sait pas convertir : aliment absent, quantité absente,
    ou unité devenue incalculable — une portion supprimée entre-temps, des
    millilitres sur un aliment mesuré en grammes.
    """
    if food is None or quantity is None:
        return None

    try:
        factor = resolve_factor(food, unit_label or "")
    except ValidationError:
        return None

    return Decimal(quantity) * factor


def merge_key(food: Food | None, source_type: str) -> tuple[int, str] | None:
    """Clé de regroupement, ou `None` quand la ligne doit rester isolée.

    Un article ajouté à la main ne fusionne jamais automatiquement : son auteur
    l'a écrit tel quel, et l'absorber dans une quantité générée le ferait
    disparaître de sa liste.
    """
    if food is None or source_type == ItemSource.MANUAL:
        return None

    return (food.pk, food.reference_unit)


@transaction.atomic
def add_lines(shopping_list: ShoppingList, lines: list[Line]) -> list[ShoppingListItem]:
    """Verse des lignes dans une liste, en fusionnant ce qui est compatible."""
    mergeable: dict[tuple[int, str], ShoppingListItem] = {}
    for item in shopping_list.items.select_related("food"):
        key = merge_key(item.food, item.source_type)
        # Un article déjà stocké dans une autre unité que celle de référence
        # n'a pas été normalisé : on ne l'absorbe pas non plus.
        if key is not None and item.quantity is not None and item.unit_label == key[1]:
            mergeable[key] = item

    touched = []
    next_order = shopping_list.items.count()

    for line in lines:
        amount = normalized_quantity(line.food, line.quantity, line.unit_label)
        key = merge_key(line.food, line.source_type) if amount is not None else None

        if key is not None and key in mergeable:
            item = mergeable[key]
            item.quantity = (item.quantity or Decimal(0)) + amount
            item.save(update_fields=["quantity"])
            touched.append(item)
            continue

        item = ShoppingListItem.objects.create(
            shopping_list=shopping_list,
            name=line.name,
            food=line.food,
            # Normalisée quand on a su convertir, brute sinon : mieux vaut une
            # ligne isolée qu'une somme inventée.
            quantity=amount if amount is not None else line.quantity,
            unit_label=key[1] if key is not None else line.unit_label,
            source_type=line.source_type,
            sort_order=next_order,
        )
        next_order += 1
        touched.append(item)

        if key is not None:
            mergeable[key] = item

    return touched


def _recipes_visible_to(user: User, recipe_ids: list[int]):
    return (
        Recipe.objects.visible_to(user)
        .filter(pk__in=recipe_ids)
        .prefetch_related("ingredients__food__portions")
    )


def lines_from_recipes(user: User, recipe_ids: list[int]) -> list[Line]:
    """Ingrédients des recettes demandées, telles que l'appelant peut les voir."""
    return [
        Line(
            name=ingredient.food_name,
            food=ingredient.food,
            quantity=ingredient.quantity,
            unit_label=ingredient.unit_label,
            source_type=ItemSource.RECIPE,
        )
        for recipe in _recipes_visible_to(user, recipe_ids)
        for ingredient in recipe.ingredients.all()
    ]


def lines_from_days(user: User, dates: list[date_type]) -> list[Line]:
    """Ce qu'il faut acheter pour reproduire ces journées.

    Une entrée de recette est **dépliée** en ingrédients, mis à l'échelle des
    portions consommées : on n'achète pas des portions de blanquette, on achète
    ce qu'il faut pour la faire.

    Un ajout rapide n'apporte rien : il n'a pas d'aliment à mettre au panier.
    """
    lines: list[Line] = []

    for day in dates:
        for entry in day_entries(user, day):
            if entry.entry_type == EntryType.QUICK_ADD:
                continue

            if entry.entry_type == EntryType.RECIPE:
                lines.extend(_recipe_entry_lines(entry))
                continue

            lines.append(
                Line(
                    name=entry.snapshot_name,
                    food=entry.food,
                    quantity=entry.quantity,
                    unit_label=entry.unit_label,
                    source_type=ItemSource.DIARY,
                )
            )

    return lines


def _recipe_entry_lines(entry) -> list[Line]:
    """Ingrédients d'une recette journalisée, à l'échelle des portions."""
    recipe = entry.recipe
    if recipe is None or not recipe.servings:
        # La recette a disparu : son snapshot ne porte pas ses ingrédients, il
        # n'y a rien à acheter qu'on puisse nommer.
        return []

    scale = Decimal(entry.quantity) / Decimal(recipe.servings)

    return [
        Line(
            name=ingredient.food_name,
            food=ingredient.food,
            quantity=Decimal(ingredient.quantity) * scale,
            unit_label=ingredient.unit_label,
            source_type=ItemSource.DIARY,
        )
        for ingredient in recipe.ingredients.all()
    ]


def lines_from_meal_plan(user: User, meal_plan_id: int) -> list[Line]:
    """Ce qu'un plan verse au panier (spec 01 §16).

    Mêmes règles qu'une journée de journal : une recette y verse ses
    **ingrédients** mis à l'échelle des portions prévues — on n'achète pas des
    portions de blanquette — et ce qui n'a plus de source ne verse rien.
    """
    from planning.models import MealPlan, PlanEntryType

    plan = MealPlan.objects.filter(pk=meal_plan_id, owner=user).first()
    if plan is None:
        return []

    lines: list[Line] = []
    entries = (
        MealPlanEntry.objects.filter(meal_plan_day__meal_plan=plan)
        .select_related("food", "recipe")
        .prefetch_related("recipe__ingredients__food")
    )

    for entry in entries:
        if entry.entry_type == PlanEntryType.FOOD and entry.food is not None:
            lines.append(
                Line(
                    name=entry.food.name,
                    food=entry.food,
                    quantity=entry.quantity,
                    unit_label=entry.unit_label,
                    source_type=ItemSource.MEAL_PLAN,
                )
            )
        elif entry.entry_type == PlanEntryType.RECIPE and entry.recipe is not None:
            lines.extend(_plan_recipe_lines(entry))

    return lines


def _plan_recipe_lines(entry) -> list[Line]:
    """Ingrédients d'une recette planifiée, à l'échelle des portions prévues."""
    recipe = entry.recipe
    servings = Decimal(recipe.servings)
    if servings <= 0:
        return []

    share = Decimal(entry.quantity) / servings

    return [
        Line(
            name=ingredient.food.name if ingredient.food else recipe.name,
            food=ingredient.food,
            quantity=Decimal(ingredient.quantity) * share,
            unit_label=ingredient.unit_label,
            source_type=ItemSource.MEAL_PLAN,
        )
        for ingredient in recipe.ingredients.all()
    ]
