"""Routes des recettes et des repas enregistrés (spec 04 §6 et §7)."""

from django.urls import path

from recipes import views

recipe_patterns = [
    path("", views.RecipeListCreateView.as_view(), name="list"),
    path("<int:pk>/", views.RecipeDetailView.as_view(), name="detail"),
    path("<int:pk>/duplicate/", views.RecipeDuplicateView.as_view(), name="duplicate"),
    path("<int:pk>/favorite/", views.RecipeFavoriteView.as_view(), name="favorite"),
    path("<int:pk>/add-to-diary/", views.RecipeAddToDiaryView.as_view(), name="add-to-diary"),
]

saved_meal_patterns = [
    path("", views.SavedMealListCreateView.as_view(), name="list"),
    path("<int:pk>/", views.SavedMealDetailView.as_view(), name="detail"),
    path("<int:pk>/duplicate/", views.SavedMealDuplicateView.as_view(), name="duplicate"),
    path("<int:pk>/add-to-diary/", views.SavedMealAddToDiaryView.as_view(), name="add-to-diary"),
]
