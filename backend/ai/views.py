"""Endpoints d'IA (spec 04 §10).

Ces vues **ne créent jamais d'entrée de journal**. Elles rendent des
suggestions ; c'est `/diary/entries/` qui écrit, une fois que l'utilisateur a
confirmé (spec 07 §5, CLAUDE.md §2).
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ai.exceptions import AIUnavailable
from ai.services import gate
from ai.services import images as image_store
from ai.services.uploads import FIELD, read_uploads
from ai.tasks import analyze_meal_task
from common.models import AsyncTask, TaskType
from common.permissions import IsActiveAccount
from common.serializers import AsyncTaskSerializer

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]

#: Durée pendant laquelle le résultat reste consultable. Au-delà, personne ne
#: viendra plus le chercher.
RESULT_RETENTION_HOURS = 24


class MealScanView(APIView):
    """`POST /ai/meal-scan/` — lance l'analyse d'une photo de repas.

    Répond 202 : l'analyse dure plusieurs secondes et se poursuit dans un
    worker. Le frontend suit son avancement par `GET /tasks/{id}/`.

    Le quota `ai` n'est pas une limite produit — la spec 07 §5 veut l'usage
    illimité pour l'utilisateur — mais une protection contre une boucle
    emballée, au titre de la spec 05 §12.
    """

    permission_classes = ACTIVE_USER
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request: Request) -> Response:
        if not gate.is_enabled():
            raise AIUnavailable()

        images = read_uploads(request.FILES.getlist(FIELD))
        keys = image_store.stash(images)

        task = AsyncTask.objects.create(
            user=request.user,
            task_type=TaskType.MEAL_SCAN,
            expires_at=timezone.now() + timedelta(hours=RESULT_RETENTION_HOURS),
        )

        analyze_meal_task.delay(str(task.pk), keys)

        # En exécution synchrone — tests, développement sans worker — la tâche
        # a déjà abouti : l'objet en mémoire serait périmé.
        task.refresh_from_db()
        return Response(AsyncTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)
