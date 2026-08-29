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


def _execute(task_id: str, work: Callable[[AsyncTask], dict], *, cleanup: Callable[[], None]):
    """Enveloppe commune à tous les traitements longs.

    `work` reçoit la tâche et rend ce qui sera rangé dans `AsyncTask.result`.
    `cleanup` s'exécute quoi qu'il arrive — y compris quand la tâche a disparu.
    """
    task = AsyncTask.objects.select_related("user").filter(pk=task_id).first()
    if task is None:
        # La tâche a disparu — compte supprimé, par exemple. Ce qu'elle avait
        # mis de côté ne doit pas lui survivre.
        cleanup()
        return

    try:
        task.status = TaskStatus.PROCESSING
        task.progress = PROCESSING_PROGRESS
        task.save(update_fields=["status", "progress", "updated_at"])

        _finish(task, status=TaskStatus.SUCCESS, result=work(task))

    except AIProviderError as error:
        # Message déjà nettoyé par la frontière IA : ni clé, ni charge utile.
        _finish(task, status=TaskStatus.FAILED, error=str(error))
    except _Abandoned as reason:
        _finish(task, status=TaskStatus.FAILED, error=str(reason))
    except Exception:
        # La trace technique est journalisée, jamais renvoyée : elle pourrait
        # citer des données privées (spec 10 §12).
        logger.exception("Échec inattendu du traitement %s", task.task_type)
        _finish(task, status=TaskStatus.FAILED, error=GENERIC_FAILURE)
    finally:
        cleanup()


class _Abandoned(Exception):
    """Renoncement décidé par le traitement, avec un message pour l'utilisateur."""


def _run(task_id: str, image_keys: list[str], work: Callable[[AsyncTask, list[ImagePart]], dict]):
    """Enveloppe des traitements d'image.

    Le point qui compte : la photo ne survit pas au traitement, que celui-ci
    ait réussi ou non (spec 07 §5).
    """

    def with_images(task: AsyncTask) -> dict:
        parts = image_store.read(image_keys)
        if not parts:
            raise _Abandoned(EXPIRED_IMAGES)
        return work(task, parts)

    _execute(task_id, with_images, cleanup=lambda: image_store.discard(image_keys))


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


#: Mesuré : une journée coûte jusqu'à une minute quand elle demande ses trois
#: essais. Une semaine tient donc en sept minutes environ, et ce délai laisse
#: de la marge sans qu'une génération partie de travers occupe le worker
#: indéfiniment. Les valeurs globales — neuf et dix minutes — seraient trop
#: courtes.
PLAN_SOFT_TIME_LIMIT = 20 * 60
PLAN_TIME_LIMIT = 22 * 60


@shared_task(ignore_result=True, soft_time_limit=PLAN_SOFT_TIME_LIMIT, time_limit=PLAN_TIME_LIMIT)
def generate_meal_plan_task(task_id: str, constraints: dict) -> None:
    """Compose une proposition de plan, une journée après l'autre.

    Rien n'est persisté : le résultat est une **proposition**, que
    `POST /meal-plans/` enregistrera une fois relue. La progression avance par
    journée — c'est la seule granularité honnête, chacune coûtant un appel au
    fournisseur, parfois trois.
    """
    from datetime import date as date_type

    from ai.services.meal_plan import build_proposal

    parsed = {
        **constraints,
        "start_date": date_type.fromisoformat(constraints["start_date"]),
        "end_date": date_type.fromisoformat(constraints["end_date"]),
    }

    def work(task: AsyncTask) -> dict:
        def progress(done: int, total: int) -> None:
            task.progress = PROCESSING_PROGRESS + int(
                (100 - PROCESSING_PROGRESS) * done / max(total, 1)
            )
            task.save(update_fields=["progress", "updated_at"])

        return build_proposal(user=task.user, constraints=parsed, on_progress=progress)

    _execute(task_id, work, cleanup=lambda: None)


@shared_task(ignore_result=True)
def regenerate_plan_meal_task(task_id: str, plan_id: int, day_id: int, meal_type_id: int) -> None:
    """Recompose un seul repas d'un plan enregistré (spec 01 §15).

    Écrit directement dans le plan : l'utilisateur l'a demandé sur son propre
    plan, et un plan n'est pas le journal. Le journal, lui, n'est jamais
    modifié sans confirmation.

    Ne puise que dans l'existant : une recette inventée ne s'enregistre qu'à
    l'acceptation d'un plan (spec 07 §8).
    """
    from ai.services.meal_plan import regenerate_meal

    def work(task: AsyncTask) -> dict:
        return regenerate_meal(
            user=task.user, plan_id=plan_id, day_id=day_id, meal_type_id=meal_type_id
        )

    _execute(task_id, work, cleanup=lambda: None)
