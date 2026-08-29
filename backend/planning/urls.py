"""Routes du planning et de la liste de courses (spec 04 §8, §11)."""

from django.urls import path

from planning import views

shopping_list_patterns = [
    path("", views.ShoppingListListCreateView.as_view(), name="list"),
    path("generate/", views.ShoppingListGenerateView.as_view(), name="generate"),
    path("<int:pk>/", views.ShoppingListDetailView.as_view(), name="detail"),
    path("<int:pk>/items/", views.ShoppingListItemCreateView.as_view(), name="items"),
    path(
        "<int:pk>/items/<int:item_id>/",
        views.ShoppingListItemDetailView.as_view(),
        name="item-detail",
    ),
]

meal_plan_patterns = [
    path("", views.MealPlanListCreateView.as_view(), name="list"),
    path("generate/", views.MealPlanGenerateView.as_view(), name="generate"),
    path("<int:pk>/", views.MealPlanDetailView.as_view(), name="detail"),
    path(
        "<int:pk>/regenerate-entry/",
        views.MealPlanRegenerateMealView.as_view(),
        name="regenerate-entry",
    ),
    path("<int:pk>/add-to-diary/", views.MealPlanAddToDiaryView.as_view(), name="add-to-diary"),
]
