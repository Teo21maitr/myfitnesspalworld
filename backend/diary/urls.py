"""Routes du journal, montées sous `/api/v1/` (spec 04 §4 et §5)."""

from django.urls import path

from . import views, views_analysis

diary_patterns = [
    path("", views.DiaryDayView.as_view(), name="day"),
    path("entries/", views.DiaryEntryCreateView.as_view(), name="entry-create"),
    path("entries/<int:pk>/", views.DiaryEntryDetailView.as_view(), name="entry-detail"),
    path(
        "entries/<int:pk>/duplicate/",
        views.DiaryEntryDuplicateView.as_view(),
        name="entry-duplicate",
    ),
    path("copy-meal/", views.DiaryCopyMealView.as_view(), name="copy-meal"),
    path("copy-day/", views.DiaryCopyDayView.as_view(), name="copy-day"),
    path("bulk-add/", views.DiaryBulkAddView.as_view(), name="bulk-add"),
]

meal_type_patterns = [
    path("", views.MealTypeListCreateView.as_view(), name="list"),
    path("reorder/", views.MealTypeReorderView.as_view(), name="reorder"),
    path("<int:pk>/", views.MealTypeDetailView.as_view(), name="detail"),
]

dashboard_patterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
]

analysis_patterns = [
    path("food/", views_analysis.FoodAnalysisView.as_view(), name="food"),
    path("weekly/", views_analysis.WeeklyAnalysisView.as_view(), name="weekly"),
]

report_patterns = [
    path("summary/", views_analysis.ReportSummaryView.as_view(), name="summary"),
    path("csv/", views_analysis.ReportCsvView.as_view(), name="csv"),
    path("pdf/", views_analysis.ReportPdfView.as_view(), name="pdf"),
]
