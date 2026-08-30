"""Notifications, préférences et rappels (spec 01 §24, spec 03 §11).

Un rappel a deux façons d'échouer, et **aucune ne lève d'exception** : partir
deux fois, ou ne pas partir. La seconde ne s'observe nulle part — rien ne
distingue « aucun rappel n'était dû » de « le rappel a été manqué ».

D'où la contrainte `notification_reminder_once_per_day` : **la notification est
la preuve** qu'un rappel est parti. Un verrou de cache n'aurait pas suffi — il
expire, disparaît au redémarrage de Redis, et n'est la source de vérité de
rien ; un worker relancé rejouerait la journée.
"""

from django.db import models
from django.db.models import Q


class EmailType(models.TextChoices):
    """Types d'emails transactionnels envoyés par l'application."""

    ACCOUNT_ACCEPTED = "ACCOUNT_ACCEPTED", "Compte accepté"
    ACCOUNT_REJECTED = "ACCOUNT_REJECTED", "Compte refusé"
    PASSWORD_RESET = "PASSWORD_RESET", "Réinitialisation du mot de passe"
    NOTIFICATION = "NOTIFICATION", "Notification"


class EmailStatus(models.TextChoices):
    SENT = "SENT", "Envoyé"
    FAILED = "FAILED", "Échec"


class EmailLog(models.Model):
    """Trace d'un email envoyé, consultable par l'administrateur (spec 05 §4).

    Ne contient jamais le corps du message, ni un token, ni un mot de passe
    (spec 05 §15). La suppression d'un compte supprime ses traces d'email.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_logs",
        verbose_name="utilisateur",
        help_text="Nul lorsque l'email ne correspond à aucun compte, par exemple un refus.",
    )
    email_type = models.CharField("type", max_length=32, choices=EmailType.choices)
    recipient = models.EmailField("destinataire")
    status = models.CharField("statut", max_length=8, choices=EmailStatus.choices)
    provider_response_summary = models.TextField(  # noqa: DJ001 - nul si aucune erreur
        "réponse du fournisseur",
        null=True,
        blank=True,
        help_text="Résumé nettoyé, utilisé pour diagnostiquer un échec.",
    )
    created_at = models.DateTimeField("envoyé le", auto_now_add=True)

    class Meta:
        verbose_name = "email envoyé"
        verbose_name_plural = "emails envoyés"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email_type", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.get_email_type_display()} → {self.recipient}"


class EventType(models.TextChoices):
    """Ce qui peut produire une notification (spec 01 §24).

    Les trois premiers sont les rappels que la spec nomme. Les trois suivants
    sont des événements sociaux qui, aujourd'hui, ne produisent que du silence.
    """

    MEAL_REMINDER = "meal_reminder", "Rappel de repas"
    WEIGH_IN_REMINDER = "weigh_in_reminder", "Rappel de pesée"
    PLAN_REMINDER = "plan_reminder", "Rappel de planification"
    FRIEND_REQUEST = "friend_request", "Demande d'ami reçue"
    FRIEND_ACCEPTED = "friend_accepted", "Demande d'ami acceptée"
    SHARE_RECEIVED = "share_received", "Partage reçu"


class ReminderType(models.TextChoices):
    """Les trois rappels réglables, et l'événement que chacun produit."""

    MEAL = "meal", "Repas"
    WEIGH_IN = "weigh_in", "Pesée"
    PLAN = "plan", "Planification"


#: Événement produit par chaque type de rappel. Écrit ici plutôt que déduit :
#: une correspondance implicite finirait par se perdre.
REMINDER_EVENTS: dict[str, str] = {
    ReminderType.MEAL: EventType.MEAL_REMINDER,
    ReminderType.WEIGH_IN: EventType.WEIGH_IN_REMINDER,
    ReminderType.PLAN: EventType.PLAN_REMINDER,
}


def all_weekdays() -> list[int]:
    """Tous les jours, par défaut. Convention Python : 0 pour lundi."""
    return [0, 1, 2, 3, 4, 5, 6]


class Reminder(models.Model):
    """Rappel réglable par l'utilisateur (spec 01 §24).

    Un seul par type et par compte : la spec le dit, et c'est une contrainte de
    base plutôt qu'une validation Python, comme partout ailleurs dans le
    projet.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name="utilisateur",
    )
    reminder_type = models.CharField("type", max_length=16, choices=ReminderType.choices)
    time = models.TimeField("heure")
    days_of_week = models.JSONField(
        "jours de la semaine",
        default=all_weekdays,
        help_text="Entiers de 0 (lundi) à 6 (dimanche), convention Python.",
    )
    enabled = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "rappel"
        verbose_name_plural = "rappels"
        ordering = ["reminder_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reminder_type"], name="reminder_unique_per_type"
            )
        ]
        indexes = [models.Index(fields=["enabled", "time"])]

    def __str__(self) -> str:
        return f"{self.get_reminder_type_display()} à {self.time:%H:%M}"

    @property
    def event_type(self) -> str:
        return REMINDER_EVENTS[self.reminder_type]


class Notification(models.Model):
    """Une notification interne (spec 03 §11).

    Quand elle vient d'un rappel, elle en porte la référence et la date visée.
    Ce couple est **unique** : c'est ce qui garantit qu'un rappel ne part
    qu'une fois, même si la tâche est rejouée après une panne.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="utilisateur",
    )
    event_type = models.CharField("événement", max_length=32, choices=EventType.choices)
    title = models.CharField("titre", max_length=120)
    message = models.CharField("message", max_length=500, blank=True, default="")
    link = models.CharField(  # noqa: DJ001 - nul quand rien à ouvrir
        "lien",
        max_length=255,
        null=True,
        blank=True,
        help_text="Chemin interne de l'application, jamais une URL externe.",
    )
    is_read = models.BooleanField("lue", default=False)
    reminder = models.ForeignKey(
        Reminder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="rappel",
        help_text="Renseigné quand la notification vient d'un rappel planifié.",
    )
    scheduled_on = models.DateField(
        "journée visée",
        null=True,
        blank=True,
        help_text="Date du rappel. Avec le rappel, forme la clé d'unicité.",
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-created_at"]
        constraints = [
            # La preuve qu'un rappel est parti, c'est cette ligne. Partielle :
            # les notifications d'événement n'ont pas de rappel, et deux
            # demandes d'ami le même jour restent deux notifications.
            models.UniqueConstraint(
                fields=["reminder", "scheduled_on"],
                condition=Q(reminder__isnull=False),
                name="notification_reminder_once_per_day",
            )
        ]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def __str__(self) -> str:
        return self.title


class NotificationPreference(models.Model):
    """Ce qu'un compte accepte de recevoir, par type d'événement (spec 01 §24).

    Une ligne absente n'est pas une préférence : les défauts vivent dans
    `services/dispatch.py`, en un seul endroit. Sans cela, la réponse à « le
    canal email est-il actif ? » dépendrait de qui pose la question.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name="utilisateur",
    )
    event_type = models.CharField("événement", max_length=32, choices=EventType.choices)
    in_app_enabled = models.BooleanField("dans l'application", default=True)
    email_enabled = models.BooleanField("par email", default=False)
    push_enabled = models.BooleanField(
        "par notification push",
        default=False,
        help_text="La colonne existe (spec 03 §11) ; aucun canal ne la lit encore.",
    )

    class Meta:
        verbose_name = "préférence de notification"
        verbose_name_plural = "préférences de notification"
        ordering = ["event_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event_type"], name="notification_preference_unique_per_event"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} — {self.user}"
