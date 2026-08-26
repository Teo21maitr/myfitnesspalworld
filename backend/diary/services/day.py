"""Construction d'une journée de journal (spec 04 §4 et §16).

Ce module est partagé par le journal et le tableau de bord. Les deux affichent
les mêmes totaux pour une même date : les recalculer chacun de son côté les
ferait tôt ou tard diverger, et l'utilisateur verrait deux chiffres différents
pour la même journée.
"""

from datetime import date as date_type
from decimal import Decimal

from accounts.models import User
from diary.models import DiaryDay, DiaryEntry
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.services.goals import resolve_for_date

#: Correspondance entre un champ d'objectif et le nutriment consommé.
GOAL_TO_NUTRIENT = {
    "daily_calories": "energy_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbohydrates_g",
    "fat_g": "fat_g",
    "fiber_g": "fiber_g",
}


def day_entries(user: User, day: date_type) -> list[DiaryEntry]:
    """Entrées d'une journée, dans l'ordre de consommation."""
    diary_day = DiaryDay.objects.filter(user=user, date=day).first()
    if diary_day is None:
        return []

    return list(
        DiaryEntry.objects.filter(diary_day=diary_day)
        .select_related("meal_type")
        .order_by("consumed_at", "id")
    )


def remaining(goals: dict | None, totals: dict) -> dict | None:
    """Ce qu'il reste à consommer. `None` tant qu'aucun objectif n'est défini."""
    if not goals:
        return None

    values = {}
    for goal_field, nutrient in GOAL_TO_NUTRIENT.items():
        target = goals.get(goal_field)
        if target is None:
            values[goal_field] = None
            continue
        values[goal_field] = Decimal(target) - Decimal(totals.get(nutrient) or 0)

    return values


def build_day(user: User, day: date_type) -> dict:
    """Journée complète : objectifs, totaux, restants et repas."""
    meals = meal_types_for(user, active_only=True).order_by("sort_order", "id")
    diary_day = DiaryDay.objects.filter(user=user, date=day).first()
    entries = day_entries(user, day)

    sections = []
    for meal in meals:
        meal_entries = [entry for entry in entries if entry.meal_type_id == meal.id]
        meal_totals, meal_incomplete = entries_service.sum_nutrition(meal_entries)
        sections.append(
            {
                "meal_type": meal,
                "entries": meal_entries,
                "totals": meal_totals,
                "incomplete_nutrients": meal_incomplete,
            }
        )

    totals, incomplete = entries_service.sum_nutrition(entries)
    goals = resolve_for_date(user, day)

    return {
        "date": day,
        "notes": diary_day.notes if diary_day else "",
        "goals": goals,
        "totals": totals,
        "incomplete_nutrients": incomplete,
        "remaining": remaining(goals, totals),
        "meals": sections,
    }
