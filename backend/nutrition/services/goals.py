"""Cycle de vie des objectifs nutritionnels (spec 01 §4).

Règle centrale : *un changement d'objectif n'est jamais rétroactif*. Créer un
objectif ne modifie donc pas le précédent, il le clôt à la veille de la
nouvelle période.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from accounts.models import User
from nutrition.models import NutritionGoal, NutritionGoalDayOverride
from nutrition.services.calculation import macro_calories


def current_goal(user: User, on: date | None = None) -> NutritionGoal | None:
    """Objectif applicable à une date donnée.

    Les contraintes du modèle garantissent qu'au plus un objectif couvre une
    date : les périodes ne se chevauchent pas.
    """
    reference = on or date.today()

    return (
        NutritionGoal.objects.filter(user=user, start_date__lte=reference)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=reference))
        .order_by("-start_date")
        .first()
    )


def resolve_for_date(user: User, on: date) -> dict | None:
    """Valeurs applicables à une date, surcharge du jour de semaine comprise.

    Un champ nul dans la surcharge reprend la valeur de l'objectif de base.
    """
    goal = current_goal(user, on)
    if goal is None:
        return None

    values = {
        "daily_calories": goal.daily_calories,
        "protein_g": goal.protein_g,
        "carbs_g": goal.carbs_g,
        "fat_g": goal.fat_g,
        "fiber_g": goal.fiber_g,
    }

    override = goal.day_overrides.filter(weekday=on.weekday(), enabled=True).first()
    if override is not None:
        for field in values:
            overridden = getattr(override, field)
            if overridden is not None:
                values[field] = overridden

    return {"goal": goal, "date": on, "weekday": on.weekday(), **values}


@transaction.atomic
def create_goal(
    user: User,
    *,
    start_date: date | None = None,
    **values,
) -> NutritionGoal:
    """Crée l'objectif applicable à partir de `start_date`.

    - si un objectif commence déjà à cette date, il est **mis à jour** : il
      n'a couvert aucune journée close, le dupliquer n'apporterait rien ;
    - sinon l'objectif en cours est clôturé la veille et un nouvel objectif
      est créé, ce qui préserve l'historique et évite tout chevauchement.
    """
    effective_date = start_date or date.today()

    existing = NutritionGoal.objects.filter(user=user, start_date=effective_date).first()
    if existing is not None:
        for field, value in values.items():
            setattr(existing, field, value)
        existing.end_date = None
        existing.full_clean()
        existing.save()
        return existing

    open_goal = NutritionGoal.objects.filter(user=user, end_date__isnull=True).first()
    if open_goal is not None:
        open_goal.end_date = effective_date - timedelta(days=1)
        open_goal.full_clean()
        open_goal.save(update_fields=["end_date"])

    goal = NutritionGoal(user=user, start_date=effective_date, **values)
    goal.full_clean()
    goal.save()
    return goal


def set_day_override(goal: NutritionGoal, weekday: int, **values) -> NutritionGoalDayOverride:
    """Crée ou met à jour la surcharge d'un jour de la semaine."""
    override, _ = NutritionGoalDayOverride.objects.update_or_create(
        nutrition_goal=goal, weekday=weekday, defaults=values
    )
    override.full_clean()
    return override


def macro_calorie_gap(goal_values: dict) -> Decimal:
    """Écart entre les calories visées et celles impliquées par les macros.

    En cas d'incohérence, les calories font foi (spec 01 §4) : l'écart est
    signalé, jamais corrigé silencieusement.
    """
    implied = macro_calories(goal_values["protein_g"], goal_values["carbs_g"], goal_values["fat_g"])
    return implied - goal_values["daily_calories"]
