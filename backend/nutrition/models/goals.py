"""Objectifs nutritionnels (spec 01 §4, spec 03 §2).

L'historique est conservé : un nouvel objectif clôt le précédent au lieu de
l'écraser, ce qui garantit qu'un changement n'est jamais rétroactif.
"""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class MacroMode(models.TextChoices):
    """Mode de saisie des macronutriments (spec 01 §4)."""

    PERCENTAGE = "percentage", "Pourcentage"
    GRAMS = "grams", "Grammes"


class ValueSource(models.TextChoices):
    """Origine d'une valeur : calculée par l'application ou saisie."""

    CALCULATED = "calculated", "Calculé"
    MANUAL = "manual", "Manuel"


class NutritionGoal(models.Model):
    """Objectif nutritionnel applicable sur une période.

    Une seule période est ouverte à la fois par utilisateur — la contrainte
    `nutrition_goal_single_open_period` le garantit en base — et les périodes
    ne se chevauchent pas puisque `start_date` est unique par utilisateur.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="nutrition_goals",
        verbose_name="utilisateur",
    )
    daily_calories = models.DecimalField("calories quotidiennes", max_digits=7, decimal_places=2)
    protein_g = models.DecimalField("protéines (g)", max_digits=6, decimal_places=2)
    carbs_g = models.DecimalField("glucides (g)", max_digits=6, decimal_places=2)
    fat_g = models.DecimalField("lipides (g)", max_digits=6, decimal_places=2)
    fiber_g = models.DecimalField(
        "fibres (g)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    macro_mode = models.CharField(
        "mode des macros", max_length=16, choices=MacroMode.choices, default=MacroMode.PERCENTAGE
    )
    calories_source = models.CharField(
        "origine des calories",
        max_length=16,
        choices=ValueSource.choices,
        default=ValueSource.CALCULATED,
    )
    macros_source = models.CharField(
        "origine des macros",
        max_length=16,
        choices=ValueSource.choices,
        default=ValueSource.CALCULATED,
    )
    start_date = models.DateField("applicable à partir du")
    end_date = models.DateField(
        "applicable jusqu'au",
        null=True,
        blank=True,
        help_text="Nul tant que l'objectif est celui en cours.",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "objectif nutritionnel"
        verbose_name_plural = "objectifs nutritionnels"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "start_date"], name="nutrition_goal_unique_start_per_user"
            ),
            # Un seul objectif en cours à la fois.
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(end_date__isnull=True),
                name="nutrition_goal_single_open_period",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="nutrition_goal_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(daily_calories__gte=0)
                & Q(protein_g__gte=0)
                & Q(carbs_g__gte=0)
                & Q(fat_g__gte=0),
                name="nutrition_goal_non_negative",
            ),
        ]
        indexes = [models.Index(fields=["user", "-start_date"])]

    def __str__(self) -> str:
        return f"{self.user.username} — {self.daily_calories} kcal à partir du {self.start_date}"

    @property
    def is_current(self) -> bool:
        return self.end_date is None

    @property
    def net_carbs_g(self) -> Decimal | None:
        """Glucides nets = glucides - fibres (spec 01 §4)."""
        if self.fiber_g is None:
            return None
        return self.carbs_g - self.fiber_g


class NutritionGoalDayOverride(models.Model):
    """Surcharge d'objectif pour un jour de la semaine (spec 01 §4).

    `weekday` suit la convention Python : lundi vaut 0 et dimanche 6. Un champ
    laissé nul reprend la valeur de l'objectif de base.
    """

    nutrition_goal = models.ForeignKey(
        NutritionGoal,
        on_delete=models.CASCADE,
        related_name="day_overrides",
        verbose_name="objectif",
    )
    weekday = models.PositiveSmallIntegerField(
        "jour de la semaine",
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="0 = lundi, 6 = dimanche.",
    )
    daily_calories = models.DecimalField(
        "calories quotidiennes", max_digits=7, decimal_places=2, null=True, blank=True
    )
    protein_g = models.DecimalField(
        "protéines (g)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    carbs_g = models.DecimalField(
        "glucides (g)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    fat_g = models.DecimalField(
        "lipides (g)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    fiber_g = models.DecimalField(
        "fibres (g)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    enabled = models.BooleanField("activée", default=True)

    class Meta:
        verbose_name = "surcharge de jour"
        verbose_name_plural = "surcharges de jour"
        ordering = ["weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["nutrition_goal", "weekday"],
                name="nutrition_goal_override_unique_weekday",
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="nutrition_goal_override_weekday_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_weekday_display_name()} — objectif {self.nutrition_goal_id}"

    def get_weekday_display_name(self) -> str:
        return WEEKDAY_NAMES[self.weekday]


WEEKDAY_NAMES = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]
