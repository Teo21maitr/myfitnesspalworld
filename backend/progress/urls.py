"""Routes du suivi de progression, montées sous `/api/v1/progress/`."""

from django.urls import path

from progress import views

progress_patterns = [
    path("weight/", views.WeightEntryListCreateView.as_view(), name="weight-list"),
    path("weight/<int:pk>/", views.WeightEntryDetailView.as_view(), name="weight-detail"),
]
