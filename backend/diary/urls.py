"""Routes du journal, montées sous `/api/v1/` (spec 04 §4 et §5)."""

from django.urls import path

from . import views

diary_patterns = [
    path("", views.DiaryDayView.as_view(), name="day"),
    path("entries/", views.DiaryEntryCreateView.as_view(), name="entry-create"),
    path("entries/<int:pk>/", views.DiaryEntryDetailView.as_view(), name="entry-detail"),
]

meal_type_patterns = [
    path("", views.MealTypeListCreateView.as_view(), name="list"),
    path("reorder/", views.MealTypeReorderView.as_view(), name="reorder"),
    path("<int:pk>/", views.MealTypeDetailView.as_view(), name="detail"),
]
