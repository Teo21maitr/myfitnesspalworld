"""Nutrition d'une recette, par portion (spec 01 §14).

Les ingrédients sont sommés puis divisés par le nombre de portions. Chaque
ingrédient passe par le même résolveur d'unités que le journal : les règles de
conversion d'un ingrédient sont celles d'un aliment, jamais de millilitres vers
des grammes sans densité connue.

La règle « inconnu n'est pas zéro » vient de `nutrition.services.aggregation`,
partagée avec le journal.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from nutrition.models.nutrients import NUTRIENT_FIELDS
from nutrition.services.aggregation import sum_values
from nutrition.services.quantities import resolve_multiplier
from recipes.models import Recipe, RecipeNutrition


def ingredient_values(ingredient) -> dict[str, Decimal | None]:
    """Apport d'un ingrédient, ou des inconnues quand il n'est plus calculable.

    Un aliment supprimé — ou une portion disparue qui rend l'unité
    incalculable — ne vaut pas zéro : il rend la recette partielle, ce que
    l'agrégation signalera.
    """
    food = ingredient.food
    nutrition = getattr(food, "nutrition", None) if food else None

    if nutrition is None:
        return dict.fromkeys(NUTRIENT_FIELDS)

    try:
        factor = resolve_multiplier(food, ingredient.quantity, ingredient.unit_label)
    except ValidationError:
        return dict.fromkeys(NUTRIENT_FIELDS)

    return {
        name: None
        if getattr(nutrition, name) is None
        else Decimal(getattr(nutrition, name)) * factor
        for name in NUTRIENT_FIELDS
    }


def compute(recipe: Recipe) -> tuple[dict[str, Decimal | None], list[str]]:
    """Valeurs pour **une** portion, et nutriments partiels."""
    ingredients = recipe.ingredients.select_related("food__nutrition").prefetch_related(
        "food__portions"
    )

    totals, incomplete = sum_values(
        (ingredient_values(ingredient) for ingredient in ingredients), NUTRIENT_FIELDS
    )

    servings = Decimal(recipe.servings)
    per_serving = {
        name: None if value is None else value / servings for name, value in totals.items()
    }

    return per_serving, incomplete


@transaction.atomic
def refresh(recipe: Recipe) -> RecipeNutrition:
    """Recalcule le cache et l'enregistre.

    Appelé explicitement à chaque écriture sur la recette ou ses ingrédients,
    plutôt que par un signal : une règle métier cachée dans un signal est déjà
    revenue cher à ce projet.
    """
    per_serving, incomplete = compute(recipe)

    nutrition, _ = RecipeNutrition.objects.update_or_create(
        recipe=recipe,
        defaults={**per_serving, "incomplete_nutrients": incomplete},
    )

    # `update_or_create` écrit en base mais laisse la recette en mémoire avec
    # l'ancien cache de sa relation inverse : la sérialiser juste après
    # renverrait les valeurs d'avant le recalcul.
    recipe.refresh_from_db()

    return nutrition


#: Annotation portant la date du dernier changement d'ingrédient.
FRESHNESS_ANNOTATION = "latest_ingredient_change"

_MISSING = object()


def annotate_freshness(queryset):
    """Ajoute de quoi juger la péremption sans une requête par recette.

    Une liste de vingt-cinq recettes ferait sinon vingt-cinq agrégats.
    """
    return queryset.annotate(**{FRESHNESS_ANNOTATION: Max("ingredients__food__updated_at")})


def ensure_fresh(recipe: Recipe) -> RecipeNutrition:
    """Cache à jour, recalculé s'il a vieilli.

    Le cache peut se périmer sans que la recette bouge : c'est l'aliment qui
    change. Corriger les valeurs d'un ingrédient laisserait sinon la recette
    afficher un total faux jusqu'à sa prochaine modification.
    """
    nutrition = getattr(recipe, "nutrition", None)
    if nutrition is None:
        return refresh(recipe)

    latest_food_change = getattr(recipe, FRESHNESS_ANNOTATION, _MISSING)
    if latest_food_change is _MISSING:
        latest_food_change = recipe.ingredients.aggregate(latest=Max("food__updated_at"))["latest"]

    if latest_food_change is not None and latest_food_change > nutrition.computed_at:
        return refresh(recipe)

    return nutrition
