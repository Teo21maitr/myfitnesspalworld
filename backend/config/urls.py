"""Routage racine.

Le health check est exposé à deux emplacements volontairement :
- `/health/` pour le healthcheck de la plateforme (spec 09 §8) ;
- `/api/v1/health/` pour le frontend, qui n'utilise que la base versionnée.
"""

from django.contrib import admin
from django.urls import include, path

from common.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/", include(("common.urls", "common"), namespace="api-v1")),
]
