"""Tâches d'entretien de l'infrastructure partagée."""

import logging

from celery import shared_task
from django.utils import timezone

from common.models import AsyncTask

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def purge_expired_tasks() -> int:
    """Supprime les tâches asynchrones arrivées à expiration.

    Un résultat de tâche n'a d'intérêt que le temps que le frontend vienne le
    chercher. Sans ce nettoyage, la table grossirait indéfiniment d'objets que
    plus personne ne lira.
    """
    deleted, _ = AsyncTask.objects.filter(expires_at__lte=timezone.now()).delete()
    if deleted:
        logger.info("%s tâche(s) asynchrone(s) expirée(s) supprimée(s)", deleted)
    return deleted
