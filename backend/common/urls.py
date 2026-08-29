"""Agrégation des routes exposées sous `/api/v1/`."""

from django.urls import include, path

from accounts.urls import account_patterns, auth_patterns, profile_patterns
from ai.urls import ai_patterns
from diary.urls import dashboard_patterns, diary_patterns, meal_type_patterns
from nutrition.urls import barcode_patterns, food_patterns, nutrition_profile_patterns
from planning.urls import meal_plan_patterns, shopping_list_patterns
from progress.urls import progress_patterns
from recipes.urls import recipe_patterns, saved_meal_patterns
from social.urls import (
    friend_patterns,
    friend_request_patterns,
    share_patterns,
    shared_patterns,
    user_patterns,
)

from .views import AsyncTaskDetailView, HealthView

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
    path("dashboard/", include((dashboard_patterns, "dashboard"))),
    path("account/", include((account_patterns, "account"))),
    path("progress/", include((progress_patterns, "progress"))),
    path("recipes/", include((recipe_patterns, "recipes"))),
    path("saved-meals/", include((saved_meal_patterns, "saved-meals"))),
    path("shopping-lists/", include((shopping_list_patterns, "shopping-lists"))),
    path("meal-plans/", include((meal_plan_patterns, "meal-plans"))),
    path("users/", include((user_patterns, "users"))),
    path("friends/", include((friend_patterns, "friends"))),
    path("friend-requests/", include((friend_request_patterns, "friend-requests"))),
    path("shares/", include((share_patterns, "shares"))),
    path("shared/", include((shared_patterns, "shared"))),
    path("ai/", include((ai_patterns, "ai"))),
    # Suivi générique des traitements longs : l'IA aujourd'hui, les
    # rapports lourds demain (spec 04 §9).
    path("tasks/<uuid:pk>/", AsyncTaskDetailView.as_view(), name="task-detail"),
]
