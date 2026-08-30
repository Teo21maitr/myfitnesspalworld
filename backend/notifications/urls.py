"""Routes des notifications, montées sous `/api/v1/` (spec 04 §19)."""

from django.urls import path

from notifications import views

notification_patterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("read-all/", views.NotificationReadAllView.as_view(), name="read-all"),
    path("<int:pk>/read/", views.NotificationReadView.as_view(), name="read"),
]

notification_preference_patterns = [
    path("", views.NotificationPreferenceView.as_view(), name="preferences"),
]

reminder_patterns = [
    path("", views.ReminderListCreateView.as_view(), name="list"),
    path("<int:pk>/", views.ReminderDetailView.as_view(), name="detail"),
]
