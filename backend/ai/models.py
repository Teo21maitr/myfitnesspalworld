"""Modèles de l'app `ai` (spec 03 §12).

Une seule table : la trace des appels au fournisseur, consultable par
l'administrateur (spec 05 §4). Les suggestions produites, elles, vivent dans
`AsyncTask` avec le reste des résultats de tâches.
"""

from django.db import models

from common.models import TaskType


class AILogStatus(models.TextChoices):
    """État d'un appel.

    `RUNNING` est écrit avant l'appel : une trace créée seulement à la fin
    manquerait précisément les appels qui n'en ont pas, ceux qui restent
    suspendus.
    """

    RUNNING = "running", "En cours"
    SUCCESS = "success", "Réussi"
    FAILED = "failed", "Échoué"


class AITaskLog(models.Model):
    """Trace d'un appel au fournisseur d'IA (spec 07 §10).

    Ce qui est conservé : qui, quel type de tâche, quel fournisseur, quel
    modèle, le résultat et la durée.

    Ce qui ne l'est **jamais** : l'image, l'audio, le prompt complet, une clé
    ou une donnée privée (spec 05 §15, spec 07 §10). Les deux résumés sont des
    descriptions courtes — « 1 image, 84 ko », « 3 aliments détectés » — et non
    le contenu échangé.
    """

    #: Les résumés servent au diagnostic, pas à l'archivage : ils sont bornés.
    SUMMARY_MAX_LENGTH = 255

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="ai_task_logs",
        verbose_name="utilisateur",
    )
    task_type = models.CharField("type de tâche", max_length=32, choices=TaskType.choices)
    status = models.CharField("statut", max_length=16, choices=AILogStatus.choices)
    provider = models.CharField("fournisseur", max_length=32)
    model = models.CharField("modèle", max_length=100)
    input_summary = models.CharField(  # noqa: DJ001 - nul si rien à résumer
        "résumé de l'entrée",
        max_length=SUMMARY_MAX_LENGTH,
        null=True,
        blank=True,
        help_text="Description de l'entrée, jamais son contenu.",
    )
    output_summary = models.CharField(  # noqa: DJ001 - nul si l'appel a échoué
        "résumé de la sortie",
        max_length=SUMMARY_MAX_LENGTH,
        null=True,
        blank=True,
    )
    error_message = models.CharField(  # noqa: DJ001 - nul si l'appel a réussi
        "erreur",
        max_length=SUMMARY_MAX_LENGTH,
        null=True,
        blank=True,
        help_text="Message nettoyé, sans trace technique ni charge utile.",
    )
    cost_estimate = models.DecimalField(
        "coût estimé",
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="En dollars, si le fournisseur permet de le calculer.",
    )
    created_at = models.DateTimeField("démarré le", auto_now_add=True)
    finished_at = models.DateTimeField("terminé le", null=True, blank=True)

    class Meta:
        verbose_name = "appel IA"
        verbose_name_plural = "appels IA"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["task_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_task_type_display()} — {self.get_status_display()}"

    @property
    def duration_seconds(self) -> float | None:
        """Durée de l'appel, `None` tant qu'il n'est pas terminé."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.created_at).total_seconds()
