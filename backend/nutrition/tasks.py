"""Tâches asynchrones de l'app nutrition.

Le rafraîchissement du cache Open Food Facts ne doit jamais faire attendre un
utilisateur : la fiche en cache lui est renvoyée immédiatement et la mise à
jour se fait derrière (spec 11 §3, CLAUDE.md §5).
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from nutrition.models import Food, FoodSource
from nutrition.services import off as off_service
from nutrition.services import off_client

logger = logging.getLogger(__name__)

#: Empêche d'empiler les tâches sur une fiche consultée plusieurs fois de
#: suite. Un peu plus long qu'un appel, bien plus court que le TTL du cache.
_LOCK_TIMEOUT_SECONDS = 300


def _lock_key(food_id: int) -> str:
    return f"off:refresh:{food_id}"


def is_stale(food: Food) -> bool:
    """Une fiche jamais rafraîchie ou trop ancienne mérite une mise à jour."""
    if food.source != FoodSource.OFF:
        return False
    if food.cache_refreshed_at is None:
        return True
    age = timezone.now() - food.cache_refreshed_at
    return age.days >= settings.OFF_CACHE_TTL_DAYS


def schedule_refresh(food: Food) -> bool:
    """Met en file un rafraîchissement si la fiche est périmée.

    Renvoie `True` si une tâche a effectivement été planifiée. La pose du
    verrou précède la mise en file : deux requêtes simultanées sur la même
    fiche ne déclenchent qu'un seul appel à la source.
    """
    if not settings.OFF_ENABLED or not is_stale(food):
        return False

    if not cache.add(_lock_key(food.pk), 1, timeout=_LOCK_TIMEOUT_SECONDS):
        return False

    refresh_off_product.delay(food.pk)
    return True


@shared_task(ignore_result=True)
def refresh_off_product(food_id: int) -> None:
    """Recharge une fiche Open Food Facts depuis la source.

    Toute panne est absorbée : la fiche en cache reste servie telle quelle et
    sera réessayée à la prochaine consultation. Une erreur de la source ne doit
    pas faire échouer la tâche en boucle.
    """
    try:
        food = Food.objects.get(pk=food_id, source=FoodSource.OFF)
    except Food.DoesNotExist:
        return

    if not food.external_id:
        return

    try:
        product = off_client.fetch_product(food.external_id)
    except off_client.ProductNotFound:
        # Le produit a disparu de la source. La fiche locale est conservée :
        # des entrées de journal peuvent s'y référer. On repousse simplement
        # la prochaine tentative.
        Food.objects.filter(pk=food.pk).update(cache_refreshed_at=timezone.now())
        return
    except off_client.OpenFoodFactsError:
        logger.info("Rafraîchissement Open Food Facts différé pour l’aliment %s", food_id)
        return

    try:
        off_service.upsert_product(product)
    except off_service.UnusableProduct:
        Food.objects.filter(pk=food.pk).update(cache_refreshed_at=timezone.now())
