"""Persistance d'un plan, et ce qu'on en tire (spec 01 §15).

Un plan n'est pas un historique : il ne stocke aucune valeur nutritionnelle et
ses totaux se recalculent à partir des fiches courantes. C'est aussi ce qui
garantit qu'un aliment corrigé après coup corrige le plan qui l'emploie.

Trois choses en sortent : des entrées de journal, une liste de courses, et —
pour les recettes que le modèle a inventées — de vraies recettes, créées
seulement à l'acceptation du plan.
"""

from datetime import date as date_type
from decimal import Decimal

from django.db import transaction

from diary.models import MealType
from diary.services.entries import create_food_entry, create_recipe_entry
from nutrition.models import Food
from planning.models import MealPlan, MealPlanDay, MealPlanEntry, PlanEntryType
from recipes.models import Recipe, RecipeIngredient
from recipes.services.nutrition import refresh


def _moment_on(day: date_type):
    """Heure courante, reportée sur la date visée (spec 01 §5)."""
    from datetime import datetime

    from django.utils import timezone

    now = timezone.localtime()
    return timezone.make_aware(datetime.combine(day, now.time().replace(microsecond=0)))


def _visible_food(user, food_id: int) -> Food | None:
    return Food.objects.visible_to(user).filter(pk=food_id).first()


@transaction.atomic
def create_recipe_from_proposal(*, user, proposal: dict) -> Recipe | None:
    """Crée une recette proposée par le modèle (spec 07 §8).

    Renvoie `None` quand aucun ingrédient ne se retrouve en base : une recette
    sans ingrédient n'a ni nutrition ni ligne de courses, et l'enregistrer
    incomplète vaudrait moins que l'écarter en le disant.

    La nutrition est calculée par le backend, jamais fournie par le modèle.
    """
    ingredients = [
        (food, item["quantity"], item["unit_label"])
        for item in proposal["ingredients"]
        if (food := _visible_food(user, item["food_id"])) is not None
    ]
    if not ingredients:
        return None

    recipe = Recipe.objects.create(
        owner=user,
        name=proposal["name"],
        instructions=proposal.get("instructions", ""),
        servings=Decimal(proposal["servings"]),
    )
    RecipeIngredient.objects.bulk_create(
        RecipeIngredient(
            recipe=recipe, food=food, quantity=quantity, unit_label=unit, sort_order=index
        )
        for index, (food, quantity, unit) in enumerate(ingredients)
    )
    refresh(recipe)
    return recipe


@transaction.atomic
def create_plan(*, user, payload: dict) -> tuple[MealPlan, list[str]]:
    """Enregistre un plan relu par l'utilisateur.

    Les recettes inédites qu'il a gardées sont créées **ici**, dans la même
    transaction : la génération n'écrit rien, elle propose (spec 07 §8).

    Renvoie le plan et les recettes qu'il a fallu écarter, nommées.
    """
    dates = [day["date"] for day in payload["days"]]
    plan = MealPlan.objects.create(
        owner=user,
        name=payload["name"],
        start_date=min(dates),
        end_date=max(dates),
        generated_by_ai=payload.get("generated_by_ai", False),
        notes=payload.get("notes", ""),
    )

    meal_types = {meal.pk: meal for meal in MealType.objects.filter(user=user)}
    created_recipes: dict[str, Recipe] = {}
    skipped: list[str] = []

    for day_payload in payload["days"]:
        day = MealPlanDay.objects.create(meal_plan=plan, date=day_payload["date"])

        for index, entry in enumerate(day_payload["entries"]):
            meal_type = meal_types.get(entry["meal_type_id"])
            if meal_type is None:
                continue

            food = recipe = None

            if entry["entry_type"] == PlanEntryType.FOOD:
                food = _visible_food(user, entry["food_id"])
                if food is None:
                    continue
            else:
                proposal = entry.get("new_recipe")
                if proposal is not None:
                    # Une même recette peut servir plusieurs jours : on ne la
                    # crée qu'une fois.
                    key = proposal["name"].casefold()
                    if key not in created_recipes:
                        made = create_recipe_from_proposal(user=user, proposal=proposal)
                        if made is None:
                            skipped.append(proposal["name"])
                            continue
                        created_recipes[key] = made
                    recipe = created_recipes[key]
                else:
                    recipe = (
                        Recipe.objects.visible_to(user)
                        .active()
                        .filter(pk=entry.get("recipe_id"))
                        .first()
                    )
                    if recipe is None:
                        continue

            MealPlanEntry.objects.create(
                meal_plan_day=day,
                meal_type=meal_type,
                entry_type=entry["entry_type"],
                food=food,
                recipe=recipe,
                quantity=entry["quantity"],
                unit_label=entry["unit_label"],
                sort_order=index,
                generated_by_ai=entry.get("generated_by_ai", False),
            )

    return plan, skipped


def filled_meals(user, plan: MealPlan) -> list[str]:
    """Repas des journées visées qui contiennent déjà des entrées.

    L'ajout au journal **n'écrase jamais** (spec 01 §15) : ces repas sont
    nommés, et l'utilisateur décide d'y ajouter par-dessus ou non.
    """
    from diary.models import DiaryEntry

    dates = list(plan.days.values_list("date", flat=True))
    existing = (
        DiaryEntry.objects.filter(diary_day__user=user, diary_day__date__in=dates)
        .select_related("meal_type")
        .values_list("diary_day__date", "meal_type__name")
        .distinct()
    )
    planned = {
        (day.date, entry.meal_type.name)
        for day in plan.days.prefetch_related("entries__meal_type")
        for entry in day.entries.all()
    }

    return sorted(
        f"{date.strftime('%d/%m')} — {meal}" for date, meal in existing if (date, meal) in planned
    )


@transaction.atomic
def add_plan_to_diary(*, user, plan: MealPlan, consumed_at=None) -> tuple[list, list[str]]:
    """Déplie le plan en entrées de journal normales et indépendantes.

    Chacune est snapshotée pour elle-même : modifier le plan ensuite ne touche
    pas ce qui a été journalisé. Un élément dont la source a disparu est ignoré
    et nommé, plutôt que de faire échouer l'ajout des autres — même arbitrage
    que le dépliage d'un repas enregistré.

    **Rien n'est remplacé** : les entrées s'ajoutent à ce que la journée
    contenait déjà.
    """
    entries = []
    skipped: list[str] = []

    days = plan.days.prefetch_related(
        "entries__meal_type",
        "entries__food__nutrition",
        "entries__food__portions",
        "entries__recipe__nutrition",
    )

    for day in days:
        # Même convention que la saisie manuelle : l'heure courante sur la date
        # visée. Un plan porte sur des jours à venir, pas sur des instants.
        moment = consumed_at or _moment_on(day.date)

        for entry in day.entries.all():
            if entry.entry_type == PlanEntryType.FOOD and entry.food is not None:
                entries.append(
                    create_food_entry(
                        user=user,
                        food=entry.food,
                        day=day.date,
                        meal_type=entry.meal_type,
                        quantity=entry.quantity,
                        unit_label=entry.unit_label,
                        consumed_at=moment,
                    )
                )
            elif entry.entry_type == PlanEntryType.RECIPE and entry.recipe is not None:
                entries.append(
                    create_recipe_entry(
                        user=user,
                        recipe=entry.recipe,
                        day=day.date,
                        meal_type=entry.meal_type,
                        servings=entry.quantity,
                        consumed_at=moment,
                    )
                )
            else:
                skipped.append(f"{day.date.strftime('%d/%m')} — {entry.meal_type.name}")

    return entries, sorted(set(skipped))


def plan_dates(plan: MealPlan) -> list[date_type]:
    return list(plan.days.values_list("date", flat=True))


def entry_values(entry: MealPlanEntry) -> dict[str, Decimal | None]:
    """Apport d'un élément planifié, calculé sur les fiches courantes.

    Un plan ne stocke pas de nutrition : corriger un aliment corrige donc les
    plans qui l'emploient, ce qu'un snapshot interdirait — mais un plan n'est
    pas un historique.
    """
    from nutrition.models.nutrients import NUTRIENT_FIELDS
    from recipes.services.nutrition import ensure_fresh, ingredient_values

    if entry.entry_type == PlanEntryType.FOOD and entry.food is not None:
        return ingredient_values(entry)

    if entry.entry_type == PlanEntryType.RECIPE and entry.recipe is not None:
        nutrition = ensure_fresh(entry.recipe)
        servings = Decimal(entry.quantity)
        return {
            name: None
            if getattr(nutrition, name, None) is None
            else Decimal(getattr(nutrition, name)) * servings
            for name in NUTRIENT_FIELDS
        }

    return dict.fromkeys(NUTRIENT_FIELDS)


def day_nutrition(day: MealPlanDay) -> tuple[dict[str, Decimal | None], list[str]]:
    """Totaux d'une journée planifiée, et nutriments partiels."""
    from nutrition.models.nutrients import NUTRIENT_FIELDS
    from nutrition.services.aggregation import sum_values

    return sum_values((entry_values(entry) for entry in day.entries.all()), NUTRIENT_FIELDS)
