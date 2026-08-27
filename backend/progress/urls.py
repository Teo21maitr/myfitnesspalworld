"""Routes du suivi de progression, montées sous `/api/v1/progress/`."""

from django.urls import path

from progress import views

progress_patterns = [
    path("weight/", views.WeightEntryListCreateView.as_view(), name="weight-list"),
    path("weight/<int:pk>/", views.WeightEntryDetailView.as_view(), name="weight-detail"),
    path(
        "measurements/",
        views.BodyMeasurementListCreateView.as_view(),
        name="measurement-list",
    ),
    path(
        "measurements/<int:pk>/",
        views.BodyMeasurementDetailView.as_view(),
        name="measurement-detail",
    ),
    path("charts/", views.ProgressChartView.as_view(), name="charts"),
]
