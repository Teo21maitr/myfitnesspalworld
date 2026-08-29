"""Parcours d'onboarding, en une opération transactionnelle (spec 04 §2).

Profil, première pesée et objectif initial : soit tout réussit, soit rien n'est
écrit. Un profil renseigné sans objectif laisserait un compte incapable
d'afficher un tableau de bord.

Le service existe pour que la vue et la commande de démonstration passent par
le **même** chemin. Un compte fabriqué autrement ne serait pas un compte que
l'application aurait pu produire, et masquerait les défauts qu'il devrait
révéler.
"""

from datetime import date as date_type
from decimal import Decimal

from django.db import transaction

from accounts.models import User
from nutrition.models import NutritionGoal
from nutrition.services import goals as goals_service
from progress.models import WeightEntry


class OnboardingAlreadyCompleted(Exception):
    """L'onboarding ne se rejoue pas : il créerait un second objectif initial.

    Exception métier, pas HTTP : la vue la traduit, la commande de démonstration
    la lit autrement.
    """


@transaction.atomic
def complete_onboarding(
    user: User,
    *,
    birth_date: date_type,
    sex_for_calculation: str,
    height_cm: Decimal,
    activity_level: str,
    goal_type: str,
    weight_kg: Decimal,
    daily_calories: Decimal,
    protein_g: Decimal,
    carbs_g: Decimal,
    fat_g: Decimal,
    goal_rate_kg_per_week: Decimal | None = None,
    target_weight_kg: Decimal | None = None,
    fiber_g: Decimal | None = None,
    calories_source: str = "calculated",
    macros_source: str = "calculated",
    on: date_type | None = None,
) -> NutritionGoal:
    """Renseigne le profil, enregistre la première pesée et crée l'objectif."""
    profile = user.profile
    if profile.onboarding_completed:
        raise OnboardingAlreadyCompleted

    today = on or date_type.today()

    profile.birth_date = birth_date
    profile.sex_for_calculation = sex_for_calculation
    profile.height_cm = height_cm
    profile.activity_level = activity_level
    profile.goal_type = goal_type
    profile.goal_rate_kg_per_week = goal_rate_kg_per_week
    profile.target_weight_kg = target_weight_kg
    profile.onboarding_completed = True
    profile.full_clean()
    profile.save()

    WeightEntry.objects.update_or_create(user=user, date=today, defaults={"weight_kg": weight_kg})

    return goals_service.create_goal(
        user,
        start_date=today,
        daily_calories=daily_calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        calories_source=calories_source,
        macros_source=macros_source,
    )
