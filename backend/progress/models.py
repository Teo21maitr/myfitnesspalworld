"""Suivi de la progression : poids et mensurations (spec 01 §19, spec 03 §10).

Les photos de progression (spec 01 §20) attendent le stockage objet, qui n'est
pas encore configuré.
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


#: Mesures corporelles facultatives, dans l'ordre d'affichage (spec 01 §19).
#:
#: Une mesure absente reste `null` : la mettre à 0 affirmerait un tour de taille
#: nul au lieu d'une donnée non saisie.
MEASUREMENT_FIELDS = (
    "waist_cm",
    "hips_cm",
    "chest_cm",
    "arm_cm",
    "thigh_cm",
    "body_fat_percent",
)


class BodyMeasurementEntry(models.Model):
    """Mensurations à une date donnée.

    Même règle que la pesée : une seule entrée par date et par utilisateur,
    une nouvelle saisie mettant à jour la précédente (spec 01 §19).

    Toutes les mesures sont facultatives, mais une entrée qui n'en porte
    aucune n'a pas de sens ; le serializer la refuse.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="body_measurements",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    waist_cm = models.DecimalField(
        "tour de taille (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    hips_cm = models.DecimalField(
        "tour de hanches (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    chest_cm = models.DecimalField(
        "tour de poitrine (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    arm_cm = models.DecimalField(
        "tour de bras (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    thigh_cm = models.DecimalField(
        "tour de cuisse (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    body_fat_percent = models.DecimalField(
        "masse grasse (%)", max_digits=4, decimal_places=1, null=True, blank=True
    )
    notes = models.TextField("note", null=True, blank=True)  # noqa: DJ001 - nulle si absente
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "mensuration"
        verbose_name_plural = "mensurations"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="body_measurement_unique_per_day"
            ),
            # Une mesure vaut `null` ou une valeur strictement positive : une
            # mesure à zéro serait une donnée manquante déguisée en mesure.
            *[
                models.CheckConstraint(
                    condition=Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__gt": 0}),
                    name=f"body_measurement_positive_{field}",
                )
                for field in MEASUREMENT_FIELDS
            ],
            models.CheckConstraint(
                condition=Q(body_fat_percent__isnull=True) | Q(body_fat_percent__lte=100),
                name="body_measurement_body_fat_at_most_100",
            ),
        ]
        indexes = [models.Index(fields=["user", "-date"])]

    def __str__(self) -> str:
        return f"{self.user.username} — mensurations du {self.date}"
