"""Agrégation des routes exposées sous `/api/v1/`."""

from django.urls import include, path

from accounts.urls import account_patterns, auth_patterns, profile_patterns
from diary.urls import diary_patterns, meal_type_patterns
from nutrition.urls import barcode_patterns, food_patterns, nutrition_profile_patterns
from progress.urls import progress_patterns

from .views import HealthView

app_name = "common"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/", include((auth_patterns, "auth"))),
    path("profile/", include((profile_patterns, "profile"))),
    # Objectifs et onboarding vivent aussi sous /profile/ (spec 04 §2) mais
    # appartiennent à l'app nutrition.
    path("profile/", include((nutrition_profile_patterns, "nutrition"))),
    path("foods/", include((food_patterns, "foods"))),
    path("barcodes/", include((barcode_patterns, "barcodes"))),
    path("diary/", include((diary_patterns, "diary"))),
    path("meal-types/", include((meal_type_patterns, "meal-types"))),
    path("account/", include((account_patterns, "account"))),
    path("progress/", include((progress_patterns, "progress"))),
]
