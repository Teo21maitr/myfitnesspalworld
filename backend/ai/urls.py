"""Routes de l'app `ai` (spec 04 §10)."""

from django.urls import path

from . import views

ai_patterns = [
    path("meal-scan/", views.MealScanView.as_view(), name="meal-scan"),
]
