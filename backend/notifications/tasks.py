"""Tâches planifiées des notifications (spec 01 §24, spec 07 §9)."""

import logging

from celery import shared_task

from notifications.services import reminders

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def send_due_reminders() -> int:
    """Envoie les rappels dus.

    Sûre à rejouer : l'unicité en base garantit qu'un rappel ne part qu'une
    fois par journée, quel que soit le nombre de passages.
    """
    sent = reminders.run()
    if sent:
        logger.info("%s rappel(s) envoyé(s).", sent)
    return sent
