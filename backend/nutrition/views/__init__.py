"""Vues de l'app nutrition, découpées par domaine."""

from .foods import (
    FoodDetailView,
    FoodFavoritesView,
    FoodFavoriteView,
    FoodFrequentView,
    FoodListCreateView,
    FoodPortionDetailView,
    FoodPortionListCreateView,
    FoodRecentView,
    FoodSearchView,
)
from .goals import (
    CalorieCalculationView,
    CurrentNutritionGoalView,
    DayOverrideView,
    NutritionGoalDetailView,
    NutritionGoalListCreateView,
    OnboardingView,
)

__all__ = [
    "CalorieCalculationView",
    "CurrentNutritionGoalView",
    "DayOverrideView",
    "FoodDetailView",
    "FoodFavoriteView",
    "FoodFavoritesView",
    "FoodFrequentView",
    "FoodListCreateView",
    "FoodPortionDetailView",
    "FoodPortionListCreateView",
    "FoodRecentView",
    "FoodSearchView",
    "NutritionGoalDetailView",
    "NutritionGoalListCreateView",
    "OnboardingView",
]
