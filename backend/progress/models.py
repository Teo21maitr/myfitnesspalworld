"""Suivi du poids (spec 01 §19, spec 03 §10).

Les mensurations et les photos de progression viendront avec l'étape
progression ; seul le poids est nécessaire ici, puisqu'il alimente le calcul
calorique.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class WeightEntry(models.Model):
    """Pesée à une date donnée.

    Une seule entrée par date et par utilisateur : une nouvelle saisie sur une
    date existante met à jour la valeur au lieu d'en créer une seconde
    (spec 01 §19).
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="weight_entries",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    weight_kg = models.DecimalField(
        "poids (kg)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    notes = models.TextField("note", null=True, blank=True)  # noqa: DJ001 - nulle si absente
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "pesée"
        verbose_name_plural = "pesées"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="weight_entry_unique_per_day"),
            models.CheckConstraint(
                condition=Q(weight_kg__gt=0), name="weight_entry_positive_weight"
            ),
        ]
        indexes = [models.Index(fields=["user", "-date"])]

    def __str__(self) -> str:
        return f"{self.user.username} — {self.weight_kg} kg le {self.date}"
