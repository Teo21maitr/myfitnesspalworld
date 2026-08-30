"""Suivi de la progression : poids, mensurations et photos (spec 01 §19-§20).

Les photos sont les seules données du projet qui vivent hors de la base. Leur
modèle ne porte donc pas l'image mais sa **clé de stockage** — et cette clé,
étant non devinable, est de fait un secret d'accès : elle ne sort jamais dans
une réponse d'API et ne se journalise pas (spec 05 §10 et §15).
"""

from decimal import Decimal

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


class PhotoType(models.TextChoices):
    """Les quatre angles de la spec 01 §20."""

    FRONT = "front", "Face"
    SIDE = "side", "Profil"
    BACK = "back", "Dos"
    OTHER = "other", "Autre"


class ProgressPhotoGroup(models.Model):
    """Les photos d'une date, et ce qui les accompagne (spec 01 §20).

    Un groupe par date : la spec parle de « plusieurs photos par date », donc
    d'un ensemble qui porte la date, la note et la pesée du jour, tandis que
    chaque photo ne porte que son fichier.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="progress_photo_groups",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    weight_kg_snapshot = models.DecimalField(
        "poids du jour (kg)",
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("20"))],
        help_text="Recopié à l'ajout : la pesée peut changer, la photo non.",
    )
    notes = models.TextField("note", null=True, blank=True)  # noqa: DJ001 - nulle si absente
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "groupe de photos"
        verbose_name_plural = "groupes de photos"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="progress_photo_group_unique_per_date"
            ),
            models.CheckConstraint(
                condition=Q(weight_kg_snapshot__isnull=True) | Q(weight_kg_snapshot__gt=0),
                name="progress_photo_group_positive_weight",
            ),
        ]
        indexes = [models.Index(fields=["user", "-date"])]

    def __str__(self) -> str:
        return f"Photos du {self.date}"


class ProgressPhoto(models.Model):
    """Une photo, désignée par sa clé de stockage.

    L'image elle-même vit dans un seau privé. La ligne ne porte que de quoi la
    retrouver — et supprimer cette ligne ne suffit donc jamais : l'objet doit
    partir avec elle (spec 01 §20).
    """

    group = models.ForeignKey(
        ProgressPhotoGroup,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="groupe",
    )
    photo_type = models.CharField(
        "angle", max_length=16, choices=PhotoType.choices, default=PhotoType.OTHER
    )
    storage_key = models.CharField(
        "clé de stockage",
        max_length=255,
        unique=True,
        help_text="Non devinable, donc secrète : elle n'apparaît dans aucune réponse d'API.",
    )
    mime_type = models.CharField("type", max_length=64)
    size_bytes = models.PositiveIntegerField("taille (octets)")
    created_at = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "photo de progression"
        verbose_name_plural = "photos de progression"
        ordering = ["photo_type", "id"]

    def __str__(self) -> str:
        return f"{self.get_photo_type_display()} — {self.group.date}"
