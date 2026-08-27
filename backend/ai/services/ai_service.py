"""Abstraction de service IA (spec 07 §2).

Toute la couche métier passe par ici : aucune vue, aucune tâche n'appelle un
fournisseur directement. C'est ce qui permettra d'ajouter la saisie vocale, le
planner et la génération de recettes en ajoutant des méthodes, sans toucher aux
fournisseurs.

Cette classe fait trois choses et rien d'autre :

1. appeler le fournisseur configuré ;
2. valider ce qu'il renvoie ;
3. laisser une trace dans `AITaskLog`, sans jamais y écrire de donnée privée.
"""

import logging

from django.utils import timezone

from ai import prompts, schemas
from ai.models import AILogStatus, AITaskLog
from ai.providers import AIProvider, AIProviderError, ImagePart, get_provider
from common.models import TaskType

logger = logging.getLogger(__name__)


def _describe_images(images: list[ImagePart]) -> str:
    """Résumé de l'entrée : sa forme, jamais son contenu (spec 07 §10)."""
    total_ko = sum(len(image.data) for image in images) // 1024
    return f"{len(images)} image(s), {total_ko} ko"


class AIService:
    """Point d'entrée unique de l'IA."""

    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider if provider is not None else get_provider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def analyze_meal(self, *, user, images: list[ImagePart], model: str) -> list[dict]:
        """Identifie les aliments d'une photo (spec 07 §5).

        Renvoie des libellés et des quantités estimées. **Aucune valeur
        nutritionnelle** : le schéma n'en prévoit pas, et la validation écarte
        ce qui n'y figure pas.
        """
        log = AITaskLog.objects.create(
            user=user,
            task_type=TaskType.MEAL_SCAN,
            status=AILogStatus.RUNNING,
            provider=self._provider.name,
            model=model,
            input_summary=_describe_images(images),
        )

        try:
            payload = self._provider.structured_completion(
                model=model,
                system=prompts.MEAL_SCAN_SYSTEM,
                prompt=prompts.MEAL_SCAN_PROMPT,
                schema=schemas.MEAL_SCAN_JSON_SCHEMA,
                images=tuple(images),
            )
            result = schemas.validate_ai_output(schemas.MealScanResultSerializer, payload)
        except AIProviderError as error:
            self._close(log, status=AILogStatus.FAILED, error=str(error))
            raise

        items = result["items"]
        self._close(log, status=AILogStatus.SUCCESS, output=f"{len(items)} aliment(s) détecté(s)")
        return items

    @staticmethod
    def _close(log: AITaskLog, *, status: str, output: str | None = None, error: str | None = None):
        log.status = status
        log.output_summary = output
        # Le message d'erreur vient de la frontière IA, qui ne recopie ni la
        # réponse du fournisseur ni la charge utile envoyée.
        log.error_message = error[: AITaskLog.SUMMARY_MAX_LENGTH] if error else None
        log.finished_at = timezone.now()
        log.save(update_fields=["status", "output_summary", "error_message", "finished_at"])
