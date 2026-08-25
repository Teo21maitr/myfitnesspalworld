"""Modèles de l'app notifications.

À cette étape, seule la journalisation des emails transactionnels est
nécessaire (spec 03 §11). `Notification`, `NotificationPreference` et
`Reminder` seront introduits avec le système de notifications complet.
"""

from django.db import models


class EmailType(models.TextChoices):
    """Types d'emails transactionnels envoyés par l'application."""

    ACCOUNT_ACCEPTED = "ACCOUNT_ACCEPTED", "Compte accepté"
    ACCOUNT_REJECTED = "ACCOUNT_REJECTED", "Compte refusé"
    PASSWORD_RESET = "PASSWORD_RESET", "Réinitialisation du mot de passe"


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
