"""Vues de l'app nutrition, découpées par domaine."""

from .external import BarcodeLookupView, ExternalFoodSearchView
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
    "BarcodeLookupView",
    "CalorieCalculationView",
    "CurrentNutritionGoalView",
    "DayOverrideView",
    "ExternalFoodSearchView",
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
