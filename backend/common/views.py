"""Vues d'infrastructure."""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

HEALTH_CACHE_KEY = "health:probe"


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:
        return False


def _check_cache() -> bool:
    try:
        cache.set(HEALTH_CACHE_KEY, "ok", timeout=10)
        return cache.get(HEALTH_CACHE_KEY) == "ok"
    except Exception:
        return False


class HealthView(APIView):
    """Health check public (spec 09 §8).

    Renvoie 200 si la base et le cache répondent, 503 sinon, afin que la
    plateforme de déploiement puisse détecter un service dégradé.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        checks = {
            "database": "ok" if _check_database() else "error",
            "cache": "ok" if _check_cache() else "error",
        }
        healthy = all(value == "ok" for value in checks.values())

        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "version": settings.APP_VERSION,
                "time": timezone.now().isoformat(),
                "checks": checks,
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
