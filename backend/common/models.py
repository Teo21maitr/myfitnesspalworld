"""Modèles d'infrastructure partagés par toutes les apps.

L'app `common` n'héberge aucune règle métier. Elle porte ici deux tables dont
plusieurs domaines ont besoin sans qu'aucun ne puisse légitimement les
posséder : la configuration globale et le suivi des tâches asynchrones.
"""

import uuid

from django.db import models


class AppSetting(models.Model):
    """Réglage global modifiable depuis l'administration (spec 03 §13).

    Une variable d'environnement n'est pas un coupe-circuit : la changer
    suppose un redéploiement. La spec 07 §11 demande qu'un administrateur
    puisse désactiver l'IA immédiatement, d'où ce réglage en base.
    """

    #: Coupe-circuit global de l'IA (spec 07 §11).
    AI_ENABLED = "ai_enabled"

    key = models.CharField("clé", max_length=100, unique=True)
    value = models.JSONField("valeur")
    description = models.TextField("description", blank=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "réglage"
        verbose_name_plural = "réglages"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key

    @classmethod
    def get_bool(cls, key: str, *, default: bool) -> bool:
        """Lit un réglage booléen, sans jamais échouer sur une valeur douteuse.

        Aucune mise en cache : un coupe-circuit doit prendre effet à l'instant
        où on l'actionne, pas à l'expiration d'un cache.
        """
        try:
            value = cls.objects.values_list("value", flat=True).get(key=key)
        except cls.DoesNotExist:
            return default
        # Un réglage saisi à la main peut contenir n'importe quoi. Seul un
        # booléen franc est retenu : le reste retombe sur la valeur par défaut
        # plutôt que d'être interprété.
        return value if isinstance(value, bool) else default


class TaskStatus(models.TextChoices):
    """États d'une tâche asynchrone (spec 04 §9)."""

    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours"
    SUCCESS = "success", "Terminée"
    FAILED = "failed", "Échouée"


class TaskType(models.TextChoices):
    """Traitements longs exposés à l'utilisateur.

    Les types de la spec 07 §9 non encore implémentés ne sont pas déclarés :
    une valeur inatteignable dans un choix suggère une fonctionnalité qui
    existe.
    """

    MEAL_SCAN = "meal_scan", "Analyse de photo de repas"
    LABEL_SCAN = "label_scan", "Lecture d'étiquette nutritionnelle"
    MEAL_PLANNER = "meal_planner", "Génération de plan de repas"


class AsyncTask(models.Model):
    """Suivi applicatif d'une tâche Celery (spec 03 §12).

    Le backend de résultats de Celery ignore la notion de propriétaire : un
    identifiant deviné y donnerait accès au résultat de n'importe qui. Cette
    table existe d'abord pour attacher une tâche à un compte, et accessoirement
    pour exposer une progression que Celery ne modélise pas.

    L'identifiant est un UUID : une clé séquentielle rendrait les tâches
    voisines énumérables, ce que la seule vérification de propriétaire suffit à
    bloquer mais qu'il est inutile d'inviter.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="async_tasks",
        verbose_name="utilisateur",
    )
    task_type = models.CharField("type", max_length=32, choices=TaskType.choices)
    status = models.CharField(
        "statut", max_length=16, choices=TaskStatus.choices, default=TaskStatus.PENDING
    )
    progress = models.PositiveSmallIntegerField("progression", default=0)
    result = models.JSONField("résultat", null=True, blank=True)
    error = models.TextField(  # noqa: DJ001 - nul tant que rien n'a échoué
        "erreur",
        null=True,
        blank=True,
        help_text="Message destiné à l'utilisateur, jamais une trace technique.",
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)
    expires_at = models.DateTimeField("expire le", null=True, blank=True)

    class Meta:
        verbose_name = "tâche asynchrone"
        verbose_name_plural = "tâches asynchrones"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.get_task_type_display()} — {self.get_status_display()}"

    @property
    def is_finished(self) -> bool:
        return self.status in {TaskStatus.SUCCESS, TaskStatus.FAILED}
