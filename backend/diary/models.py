"""Journal alimentaire (spec 01 §5, §6 et §12, spec 03 §4).

Le point structurant de ce module est la nature du snapshot. Une entrée
n'enregistre pas ce qui a été consommé, mais les valeurs **pour la quantité de
référence** de l'aliment, accompagnées de la quantité et de l'unité :

    consommé = snapshot_energy_kcal * (quantité convertie / snapshot_reference_amount)

Enregistrer directement « 385 kcal » rendrait impossible la modification
ultérieure de la quantité : il faudrait retourner interroger l'aliment source,
qui a pu changer ou disparaître. Avec les valeurs de référence, une entrée
vieille de six mois se recalcule depuis elle seule.

C'est ce qui réconcilie les deux exigences de la spec : le journal reste
modifiable dans le passé (§5), et une modification de la source ne change
jamais l'historique (§6).
"""

from django.db import models
from django.db.models import Q

from nutrition.models import FoodNutrition, UnitType


class MealSystemKey(models.TextChoices):
    """Les quatre repas par défaut (spec 01 §5).

    Ils sont désactivables mais jamais supprimés physiquement : leur clé sert
    à les reconnaître même après un renommage.
    """

    BREAKFAST = "breakfast", "Petit-déjeuner"
    LUNCH = "lunch", "Déjeuner"
    DINNER = "dinner", "Dîner"
    SNACKS = "snacks", "Collations"


class EntryType(models.TextChoices):
    """Nature d'une entrée de journal (spec 03 §4).

    `RECIPE` est déclaré dès maintenant bien qu'inutilisable : l'app recettes
    n'a pas encore de modèle. Le prévoir évite une migration de données quand
    elle arrivera.
    """

    FOOD = "food", "Aliment"
    RECIPE = "recipe", "Recette"
    QUICK_ADD = "quick_add", "Ajout rapide"


class MealType(models.Model):
    """Repas d'une journée, propre à chaque utilisateur.

    Les quatre types par défaut sont créés par utilisateur plutôt que
    partagés : chacun peut les renommer, les réordonner et les désactiver sans
    affecter les autres comptes.

    `user` reste nullable pour rester compatible avec la spec 03 §4, qui
    autorise des types globaux.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="meal_types",
        verbose_name="utilisateur",
    )
    system_key = models.CharField(  # noqa: DJ001 - nul pour un repas créé par l'utilisateur
        "clé système",
        max_length=16,
        choices=MealSystemKey.choices,
        null=True,
        blank=True,
        help_text="Renseignée pour les quatre repas par défaut.",
    )
    name = models.CharField("nom", max_length=60)
    slug = models.SlugField("identifiant", max_length=60)
    sort_order = models.PositiveSmallIntegerField("ordre", default=0)
    is_default = models.BooleanField("repas par défaut", default=False)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "type de repas"
        verbose_name_plural = "types de repas"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "slug"], name="meal_type_unique_slug"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_system(self) -> bool:
        """Un repas système se désactive, il ne se supprime pas (spec 04 §5)."""
        return self.system_key is not None


class DiaryDay(models.Model):
    """Journée de journal. Créée à la volée au premier ajout."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="diary_days",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    notes = models.TextField("notes", blank=True, default="")
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "journée"
        verbose_name_plural = "journées"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="diary_day_unique_per_user"),
        ]
        indexes = [models.Index(fields=["user", "-date"], name="diary_day_user_date")]

    def __str__(self) -> str:
        return f"{self.user} — {self.date:%d/%m/%Y}"


class DiaryEntry(models.Model):
    """Aliment, recette ou ajout rapide consommé un jour donné.

    Les champs `snapshot_*` sont les données historiques de vérité : ils
    survivent à la modification comme à la suppression de leur source
    (spec 01 §6).
    """

    diary_day = models.ForeignKey(
        DiaryDay, on_delete=models.CASCADE, related_name="entries", verbose_name="journée"
    )
    # `CASCADE` et non `PROTECT` : les repas appartiennent à l'utilisateur et
    # disparaissent avec lui. Une protection au niveau de la base bloquerait
    # toute suppression de compte — y compris depuis l'admin — car le
    # collecteur de Django la rencontre avant d'avoir supprimé les entrées.
    #
    # La garantie « on ne perd jamais d'historique » vit donc dans le service
    # `meal_types.remove()`, qui désactive un repas déjà utilisé au lieu de le
    # supprimer.
    meal_type = models.ForeignKey(
        MealType, on_delete=models.CASCADE, related_name="entries", verbose_name="repas"
    )
    entry_type = models.CharField(
        "type", max_length=16, choices=EntryType.choices, default=EntryType.FOOD
    )
    consumed_at = models.DateTimeField(
        "consommé à", help_text="Horodaté automatiquement à l'ajout, modifiable ensuite."
    )
    quantity = models.DecimalField("quantité", max_digits=10, decimal_places=3)
    unit_label = models.CharField("unité", max_length=40)
    note = models.CharField("note", max_length=255, blank=True, default="")

    # Référence facultative vers la source. `SET_NULL` plutôt que `CASCADE` :
    # la suppression d'un aliment — y compris celle du compte qui le possède —
    # ne doit jamais emporter l'historique de qui l'a consommé.
    food = models.ForeignKey(
        "nutrition.Food",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diary_entries",
        verbose_name="aliment",
    )

    # --- Snapshot : identité ---
    snapshot_name = models.CharField("nom", max_length=255)
    snapshot_brand = models.CharField("marque", max_length=255, blank=True, default="")
    snapshot_source = models.CharField("source", max_length=16)
    snapshot_reference_amount = models.DecimalField(
        "quantité de référence", max_digits=10, decimal_places=3, default=100
    )
    snapshot_reference_unit = models.CharField(
        "unité de référence", max_length=8, choices=UnitType.choices, default=UnitType.GRAM
    )
    snapshot_unit_factor = models.DecimalField(
        "valeur d'une unité saisie",
        max_digits=12,
        decimal_places=4,
        default=1,
        help_text=(
            "Combien d'unités de référence vaut une unité saisie. Figé à l'ajout pour que "
            "l'entrée reste calculable même si l'aliment ou sa portion disparaît."
        ),
    )

    # --- Snapshot : nutrition, pour la quantité de référence ---
    # Miroir de `FoodNutrition`. Des colonnes typées plutôt qu'un JSON : Food
    # Analysis devra les agréger sur des périodes entières (spec 01 §21).
    # Toutes nullables : une valeur inconnue le reste (spec 01 §8).
    snapshot_energy_kcal = models.DecimalField(
        "énergie (kcal)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_protein_g = models.DecimalField(
        "protéines (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_carbohydrates_g = models.DecimalField(
        "glucides (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_fat_g = models.DecimalField(
        "lipides (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_fiber_g = models.DecimalField(
        "fibres (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_sugars_g = models.DecimalField(
        "sucres (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_sodium_mg = models.DecimalField(
        "sodium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_salt_g = models.DecimalField(
        "sel (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_cholesterol_mg = models.DecimalField(
        "cholestérol (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_potassium_mg = models.DecimalField(
        "potassium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_calcium_mg = models.DecimalField(
        "calcium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_iron_mg = models.DecimalField(
        "fer (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_magnesium_mg = models.DecimalField(
        "magnésium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_a_ug = models.DecimalField(
        "vitamine A (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_b6_mg = models.DecimalField(
        "vitamine B6 (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_b12_ug = models.DecimalField(
        "vitamine B12 (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_c_mg = models.DecimalField(
        "vitamine C (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_d_ug = models.DecimalField(
        "vitamine D (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_e_mg = models.DecimalField(
        "vitamine E (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    snapshot_vitamin_k_ug = models.DecimalField(
        "vitamine K (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )

    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "entrée de journal"
        verbose_name_plural = "entrées de journal"
        ordering = ["consumed_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="diary_entry_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(snapshot_reference_amount__gt=0),
                name="diary_entry_reference_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["diary_day", "meal_type"], name="diary_entry_day_meal"),
        ]

    def __str__(self) -> str:
        return f"{self.snapshot_name} — {self.quantity} {self.unit_label}"


#: Champs nutritionnels du snapshot, dérivés de `FoodNutrition` dont ils sont
#: le miroir. Les nommer ainsi plutôt que de les lister à la main garantit que
#: la copie ne peut pas oublier un nutriment ajouté plus tard côté aliment.
SNAPSHOT_NUTRIENT_FIELDS = [
    f"snapshot_{field.name}"
    for field in FoodNutrition._meta.fields
    if field.name not in {"id", "food"}
]
