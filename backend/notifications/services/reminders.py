"""Déclenchement des rappels planifiés (spec 01 §24).

Balayage périodique : la tâche demande « qu'est-ce qui était dû ? » plutôt que
de programmer un envoi par rappel. Un envoi programmé se perd au redémarrage ;
une question posée toutes les cinq minutes, non.

Deux règles gouvernent ce module :

1. **un rappel ne part qu'une fois** — garanti par la contrainte d'unicité, pas
   par ce code ;
2. **un rappel manqué ne se rattrape pas indéfiniment** — au-delà de la
   fenêtre, il est sauté et journalisé. « Pense à te peser ce matin » à midi
   n'est plus un rappel, c'est du bruit.
"""

import logging
from datetime import datetime, timedelta

from django.utils import timezone

from notifications.models import Reminder
from notifications.services import dispatch

logger = logging.getLogger(__name__)

#: Au-delà, un rappel manqué est sauté plutôt qu'envoyé en retard.
CATCH_UP = timedelta(hours=1)

#: Ce que dit chaque rappel. Le lien mène là où l'action se fait.
MESSAGES: dict[str, tuple[str, str, str]] = {
    "meal": ("C'est l'heure de journaliser", "Votre repas vous attend.", "/journal"),
    "weigh_in": ("Pesée du jour", "Une pesée par jour suffit à voir la tendance.", "/progression"),
    "plan": (
        "Votre planification",
        "Le plan de la semaine est prêt à être suivi.",
        "/planification",
    ),
}


def run(now: datetime | None = None) -> int:
    """Envoie les rappels dus. Renvoie le nombre de notifications créées.

    Sûre à rejouer : deux passages dans la même journée ne produisent qu'une
    notification par rappel.
    """
    moment = now or timezone.now()
    local = timezone.localtime(moment)
    today = local.date()
    weekday = today.weekday()

    sent = 0

    for reminder in Reminder.objects.filter(enabled=True).select_related("user"):
        if weekday not in (reminder.days_of_week or []):
            continue

        due = timezone.make_aware(datetime.combine(today, reminder.time), local.tzinfo)
        if due > local:
            # Pas encore l'heure.
            continue

        if local - due > CATCH_UP:
            logger.info(
                "Rappel %s du compte %s sauté : hors fenêtre de rattrapage.",
                reminder.reminder_type,
                reminder.user_id,
            )
            continue

        title, message, link = MESSAGES[reminder.reminder_type]
        notification = dispatch.notify(
            reminder.user,
            event_type=reminder.event_type,
            title=title,
            message=message,
            link=link,
            reminder=reminder,
            on=today,
        )
        if notification is not None:
            sent += 1

    return sent
