"""Tâches asynchrones de l'app `ai` (spec 07 §9).

L'analyse d'une photo prend plusieurs secondes : elle ne peut pas se faire dans
le cycle d'une requête HTTP. La tâche fait avancer un `AsyncTask` que le
frontend interroge, et **supprime les images quoi qu'il arrive**.

Les deux traitements partagent la même enveloppe — relire les images, faire
avancer la tâche, absorber les pannes, effacer les photos. Seul le travail au
milieu diffère.
"""

import logging
from collections.abc import Callable

from celery import shared_task
from django.conf import settings

from ai.providers import AIProviderError, ImagePart
from ai.services import images as image_store
from ai.services.ai_service import AIService
from ai.services.label_scan import build_draft
from ai.services.meal_scan import build_suggestions
from common.models import AsyncTask, TaskStatus

logger = logging.getLogger(__name__)

#: Progression annoncée pendant l'appel au fournisseur. Une seule étape :
#: mentir sur une granularité qu'on n'a pas ne rendrait pas l'attente plus
#: courte.
PROCESSING_PROGRESS = 30

GENERIC_FAILURE = "L'analyse de la photo a échoué. Réessayez dans un instant."

EXPIRED_IMAGES = "Les photos ont expiré avant d'être analysées. Réessayez."


def _finish(task: AsyncTask, *, status: str, result=None, error: str | None = None) -> None:
    task.status = status
    task.progress = 100
    task.result = result
    task.error = error
    task.save(update_fields=["status", "progress", "result", "error", "updated_at"])


def _run(task_id: str, image_keys: list[str], work: Callable[[AsyncTask, list[ImagePart]], dict]):
    """Enveloppe commune aux traitements d'image.

    `work` reçoit la tâche et les images, et rend ce qui sera rangé dans
    `AsyncTask.result`.
    """
    task = AsyncTask.objects.select_related("user").filter(pk=task_id).first()
    if task is None:
        # La tâche a disparu — compte supprimé, par exemple. Les images ne
        # doivent pas lui survivre.
        image_store.discard(image_keys)
        return

    try:
        parts = image_store.read(image_keys)
        if not parts:
            _finish(task, status=TaskStatus.FAILED, error=EXPIRED_IMAGES)
            return

        task.status = TaskStatus.PROCESSING
        task.progress = PROCESSING_PROGRESS
        task.save(update_fields=["status", "progress", "updated_at"])

        _finish(task, status=TaskStatus.SUCCESS, result=work(task, parts))

    except AIProviderError as error:
        # Message déjà nettoyé par la frontière IA : ni clé, ni charge utile.
        _finish(task, status=TaskStatus.FAILED, error=str(error))
    except Exception:
        # La trace technique est journalisée, jamais renvoyée : elle pourrait
        # citer des données privées (spec 10 §12).
        logger.exception("Échec inattendu du traitement %s", task.task_type)
        _finish(task, status=TaskStatus.FAILED, error=GENERIC_FAILURE)
    finally:
        # Le point qui compte : la photo ne survit pas au traitement, que
        # celui-ci ait réussi ou non (spec 07 §5).
        image_store.discard(image_keys)


@shared_task(ignore_result=True)
def analyze_meal_task(task_id: str, image_keys: list[str]) -> None:
    """Analyse la photo d'un repas et range les suggestions dans la tâche."""

    def work(task: AsyncTask, parts: list[ImagePart]) -> dict:
        items = AIService().analyze_meal(
            user=task.user, images=parts, model=settings.AI_MEAL_SCAN_MODEL
        )
        return {"suggestions": build_suggestions(task.user, items)}

    _run(task_id, image_keys, work)


@shared_task(ignore_result=True)
def read_label_task(task_id: str, image_keys: list[str]) -> None:
    """Recopie une étiquette nutritionnelle et range le brouillon dans la tâche."""

    def work(task: AsyncTask, parts: list[ImagePart]) -> dict:
        result = AIService().read_label(
            user=task.user, images=parts, model=settings.AI_LABEL_SCAN_MODEL
        )
        return build_draft(result)

    _run(task_id, image_keys, work)
