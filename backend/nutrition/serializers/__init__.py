"""Serializers de l'app nutrition, découpés par domaine."""

from .foods import (
    ExternalFoodCandidateSerializer,
    FoodDetailSerializer,
    FoodListSerializer,
    FoodNutritionSerializer,
    FoodPortionSerializer,
    FoodWriteSerializer,
)
from .goals import (
    CalorieCalculationSerializer,
    CalorieEstimateSerializer,
    DailyValuesSerializer,
    DayOverrideSerializer,
    NutritionGoalSerializer,
    NutritionGoalWriteSerializer,
    OnboardingSerializer,
)

__all__ = [
    "CalorieCalculationSerializer",
    "CalorieEstimateSerializer",
    "DailyValuesSerializer",
    "DayOverrideSerializer",
    "ExternalFoodCandidateSerializer",
    "FoodDetailSerializer",
    "FoodListSerializer",
    "FoodNutritionSerializer",
    "FoodPortionSerializer",
    "FoodWriteSerializer",
    "NutritionGoalSerializer",
    "NutritionGoalWriteSerializer",
    "OnboardingSerializer",
]
