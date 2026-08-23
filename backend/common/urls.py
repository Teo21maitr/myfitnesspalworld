"""Routes exposées sous `/api/v1/`."""

from django.urls import path

from .views import HealthView

app_name = "common"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
]
