"""Routes des objectifs nutritionnels, montées sous `/api/v1/profile/`."""

from django.urls import path

from nutrition import views

nutrition_profile_patterns = [
    path("onboarding/", views.OnboardingView.as_view(), name="onboarding"),
    path("goals/", views.NutritionGoalListCreateView.as_view(), name="goals"),
    path("goals/calculate/", views.CalorieCalculationView.as_view(), name="goals-calculate"),
    path("goals/current/", views.CurrentNutritionGoalView.as_view(), name="goals-current"),
    path("goals/<int:pk>/", views.NutritionGoalDetailView.as_view(), name="goal-detail"),
    path(
        "goals/<int:pk>/overrides/<int:weekday>/",
        views.DayOverrideView.as_view(),
        name="goal-override",
    ),
]
