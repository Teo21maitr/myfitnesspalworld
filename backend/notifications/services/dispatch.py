"""Émission d'une notification, et préférences (spec 01 §24, spec 03 §11).

**Une préférence absente n'est pas une préférence.** Un compte qui n'a jamais
ouvert ses réglages n'a aucune ligne en base — et si chaque appelant décidait
lui-même du défaut, la réponse à « le canal email est-il actif ? » dépendrait de
qui pose la question. Les défauts vivent donc ici, en une table, lue par une
seule fonction.

Le canal push existe dans le modèle (spec 03 §11) mais **aucun canal ne le
lit** : la PWA n'a pas de service worker éditable, et une case qui ne fait rien
serait pire qu'une case grisée.
"""

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from accounts.models import User
from notifications.models import EventType, Notification, NotificationPreference

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Channels:
    """Ce qu'un compte accepte pour un type d'événement."""

    in_app: bool
    email: bool
    push: bool = False


#: Défauts, en un seul endroit.
#:
#: Les rappels ne partent **pas** par email : un « pense à journaliser ton
#: déjeuner » quotidien devient vite du bruit qu'on filtre, et une boîte filtrée
#: ne rappelle plus rien. Les événements sociaux, rares, y ont droit.
DEFAULTS: dict[str, Channels] = {
    EventType.MEAL_REMINDER: Channels(in_app=True, email=False),
    EventType.WEIGH_IN_REMINDER: Channels(in_app=True, email=False),
    EventType.PLAN_REMINDER: Channels(in_app=True, email=False),
    EventType.FRIEND_REQUEST: Channels(in_app=True, email=True),
    EventType.FRIEND_ACCEPTED: Channels(in_app=True, email=True),
    EventType.SHARE_RECEIVED: Channels(in_app=True, email=True),
}


def preferences_for(user: User) -> dict[str, Channels]:
    """Les six types, défauts comblés.

    Toujours les six clés : un appelant n'a pas à distinguer « type absent » de
    « type désactivé ».
    """
    stored = {
        row.event_type: Channels(
            in_app=row.in_app_enabled, email=row.email_enabled, push=row.push_enabled
        )
        for row in NotificationPreference.objects.filter(user=user)
    }

    return {event: stored.get(event, default) for event, default in DEFAULTS.items()}


def notify(
    user: User,
    *,
    event_type: str,
    title: str,
    message: str = "",
    link: str | None = None,
    reminder=None,
    on=None,
) -> Notification | None:
    """Émet une notification si l'utilisateur l'accepte.

    Renvoie `None` quand rien n'est créé — canal coupé, ou rappel déjà parti.

    L'`IntegrityError` sur `notification_reminder_once_per_day` est **attendue**
    et signifie « déjà envoyé aujourd'hui ». Elle se traite ici : la remonter
    ferait échouer la tâche pour un cas normal.
    """
    channels = preferences_for(user)[event_type]

    if not channels.in_app:
        return None

    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                user=user,
                event_type=event_type,
                title=title,
                message=message,
                link=link,
                reminder=reminder,
                scheduled_on=on,
            )
    except IntegrityError:
        # Déjà parti pour cette journée. Rien à faire, rien à signaler.
        return None

    if channels.email:
        _send_email(user, title=title, message=message)

    return notification


def unread_count(user: User) -> int:
    return Notification.objects.filter(user=user, is_read=False).count()


def _send_email(user: User, *, title: str, message: str) -> None:
    """Relais email, silencieux en cas d'échec.

    Une notification interne réussie ne doit pas être défaite parce que le
    serveur d'emails est indisponible : l'échec est journalisé par le service
    d'envoi, qui en garde une trace.
    """
    from notifications.services.email import send_notification_email

    send_notification_email(user, title=title, message=message)
