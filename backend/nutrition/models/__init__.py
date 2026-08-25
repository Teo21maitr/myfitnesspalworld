"""Modèles de l'app nutrition.

Le module est découpé par domaine — objectifs d'un côté, aliments de l'autre —
et réexporte l'ensemble pour que les imports existants restent valides.
"""

from .foods import (
    Food,
    FoodNutrition,
    FoodPortion,
    FoodSource,
    FoodVisibility,
    UnitType,
    UserFoodFavorite,
    UserFoodHistory,
    normalize_search_text,
)
from .goals import (
    WEEKDAY_NAMES,
    MacroMode,
    NutritionGoal,
    NutritionGoalDayOverride,
    ValueSource,
)

__all__ = [
    "WEEKDAY_NAMES",
    "Food",
    "FoodNutrition",
    "FoodPortion",
    "FoodSource",
    "FoodVisibility",
    "MacroMode",
    "NutritionGoal",
    "NutritionGoalDayOverride",
    "UnitType",
    "UserFoodFavorite",
    "UserFoodHistory",
    "ValueSource",
    "normalize_search_text",
]
