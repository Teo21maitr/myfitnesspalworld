"""Routes de l'app `ai` (spec 04 §10)."""

from django.urls import path

from . import views

ai_patterns = [
    path("status/", views.AIStatusView.as_view(), name="status"),
    path("meal-scan/", views.MealScanView.as_view(), name="meal-scan"),
    path("label-scan/", views.LabelScanView.as_view(), name="label-scan"),
]
