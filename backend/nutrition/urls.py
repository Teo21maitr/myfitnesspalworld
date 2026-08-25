"""Routes de l'app nutrition, montées sous `/api/v1/`."""

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

food_patterns = [
    path("search/", views.FoodSearchView.as_view(), name="search"),
    path("recent/", views.FoodRecentView.as_view(), name="recent"),
    path("frequent/", views.FoodFrequentView.as_view(), name="frequent"),
    path("favorites/", views.FoodFavoritesView.as_view(), name="favorites"),
    path("", views.FoodListCreateView.as_view(), name="list"),
    path("<int:pk>/", views.FoodDetailView.as_view(), name="detail"),
    path("<int:pk>/favorite/", views.FoodFavoriteView.as_view(), name="favorite"),
    path("<int:pk>/portions/", views.FoodPortionListCreateView.as_view(), name="portions"),
    path(
        "<int:pk>/portions/<int:portion_id>/",
        views.FoodPortionDetailView.as_view(),
        name="portion-detail",
    ),
]
