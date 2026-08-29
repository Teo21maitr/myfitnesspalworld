"""Planning et liste de courses (spec 01 §15-16, spec 03 §7-8).

Les deux vivent dans la même app : prévoir ses repas et savoir quoi acheter
appartiennent au même domaine, et le second se déduit du premier.

Une liste est un brouillon, pas un historique : elle se supprime franchement,
sans suppression douce, et rien ne la référence ensuite.
"""

from django.db import models
from django.db.models import F, Q


class ShoppingVisibility(models.TextChoices):
    """Visibilité d'une liste (spec 01 §18).

    Reprend les valeurs des autres énumérations métier sans les réutiliser :
    partager une énumération imposerait un `AlterField` sur des tables déjà en
    production pour un gain cosmétique.
    """

    PRIVATE = "private", "Privé"
    SPECIFIC_USERS = "specific_users", "Utilisateurs choisis"
    APP_USERS = "app_users", "Tous les utilisateurs actifs"


class ItemSource(models.TextChoices):
    """D'où vient un article (spec 03 §8).

    `MEAL_PLAN` est déclaré sans être atteignable : le planner n'existe pas
    encore, et le prévoir évite une migration de données quand il arrivera.
    """

    MANUAL = "manual", "Ajouté à la main"
    RECIPE = "recipe", "Recette"
    MEAL_PLAN = "meal_plan", "Planning"
    DIARY = "diary", "Journal"


class ShoppingListQuerySet(models.QuerySet):
    """Filtres de visibilité, sans suppression douce à écarter."""

    def visible_to(self, user):
        """Ce qu'un utilisateur a le droit de consulter (spec 05 §7)."""
        # Import tardif : `social` résout les ressources des apps métier, et
        # l'importer au chargement des modèles créerait un cycle.
        from social.models import ResourceType
        from social.services.sharing import visibility_filter

        return self.filter(visibility_filter(user, ResourceType.SHOPPING_LIST))

    def editable_by(self, user):
        return self.filter(owner=user)


class ShoppingList(models.Model):
    """Liste de courses d'un utilisateur."""

    #: Type de ressource sous lequel cette table se partage (spec 03 §9).
    SHARE_RESOURCE_TYPE = "shopping_list"

    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="shopping_lists",
        verbose_name="propriétaire",
    )
    name = models.CharField("nom", max_length=255)
    visibility = models.CharField(
        "visibilité",
        max_length=16,
        choices=ShoppingVisibility.choices,
        default=ShoppingVisibility.PRIVATE,
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)

    objects = ShoppingListQuerySet.as_manager()

    class Meta:
        verbose_name = "liste de courses"
        verbose_name_plural = "listes de courses"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "-created_at"], name="shopping_list_owner")]

    def __str__(self) -> str:
        return self.name


class ShoppingListItem(models.Model):
    """Article d'une liste.

    `food` reste facultatif : un article ajouté à la main n'en a pas, et un
    ingrédient dont l'aliment a disparu garde son nom sans en avoir un non plus.

    `quantity` et `unit_label` sont nullables pour la même raison : « du sel »
    est un article valable, et inventer « 1 unité » serait une donnée qu'on n'a
    pas (spec 01 §8).
    """

    shopping_list = models.ForeignKey(
        ShoppingList, on_delete=models.CASCADE, related_name="items", verbose_name="liste"
    )
    name = models.CharField("nom", max_length=255)
    food = models.ForeignKey(
        "nutrition.Food",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_items",
        verbose_name="aliment",
    )
    quantity = models.DecimalField(
        "quantité", max_digits=10, decimal_places=3, null=True, blank=True
    )
    unit_label = models.CharField(  # noqa: DJ001 - nulle quand la quantité l'est
        "unité", max_length=40, null=True, blank=True
    )
    is_checked = models.BooleanField("acheté", default=False)
    sort_order = models.PositiveIntegerField("ordre", default=0)
    source_type = models.CharField(
        "provenance", max_length=16, choices=ItemSource.choices, default=ItemSource.MANUAL
    )

    class Meta:
        verbose_name = "article"
        verbose_name_plural = "articles"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__isnull=True) | Q(quantity__gt=0),
                name="shopping_item_positive_quantity",
            ),
        ]

    def __str__(self) -> str:
        if self.quantity is None:
            return self.name
        return f"{self.quantity} {self.unit_label or ''} {self.name}".strip()


class PlanEntryType(models.TextChoices):
    """Nature d'une entrée de planning (spec 03 §7).

    `SAVED_MEAL` est déclaré sans être produit par la génération : l'utilisateur
    peut vouloir poser un repas enregistré dans son plan, et le prévoir évite
    une migration de données le jour où l'interface le proposera.
    """

    FOOD = "food", "Aliment"
    RECIPE = "recipe", "Recette"
    SAVED_MEAL = "saved_meal", "Repas enregistré"


class MealPlan(models.Model):
    """Plan de repas sur une période (spec 01 §15).

    Un plan est une **intention**, pas un historique : rien ne le référence, et
    le journal qu'on en tire est fait d'entrées indépendantes et snapshotées.
    Il se supprime donc franchement, comme la liste de courses.
    """

    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="meal_plans",
        verbose_name="propriétaire",
    )
    name = models.CharField("nom", max_length=255)
    start_date = models.DateField("début")
    end_date = models.DateField("fin")
    generated_by_ai = models.BooleanField("généré par IA", default=False)
    notes = models.TextField("notes", blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "planning"
        verbose_name_plural = "plannings"
        ordering = ["-start_date", "-id"]
        indexes = [models.Index(fields=["owner", "-start_date"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="meal_plan_ordered_dates",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class MealPlanDay(models.Model):
    """Une journée du plan."""

    meal_plan = models.ForeignKey(
        MealPlan, on_delete=models.CASCADE, related_name="days", verbose_name="planning"
    )
    date = models.DateField("date")

    class Meta:
        verbose_name = "journée planifiée"
        verbose_name_plural = "journées planifiées"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["meal_plan", "date"], name="meal_plan_day_unique_date"),
        ]

    def __str__(self) -> str:
        return f"{self.meal_plan.name} — {self.date}"


class MealPlanEntry(models.Model):
    """Un élément prévu à un repas d'une journée.

    Aucune valeur nutritionnelle n'est stockée ici, à la différence d'une entrée
    de journal : un plan n'est pas un historique, et ses totaux se recalculent à
    partir des fiches courantes. C'est aussi ce qui garantit que la tolérance
    porte sur la base et non sur ce qu'un modèle a annoncé.

    Les sources sont en `SET_NULL`, comme celle d'un article de courses : un
    aliment supprimé doit laisser un trou **visible** dans le plan, pas le faire
    rétrécir en silence. La cohérence entre `entry_type` et sa source est
    vérifiée à l'écriture par le serializer ; une contrainte de base
    l'imposerait aussi après coup, et interdirait précisément ce trou.
    """

    meal_plan_day = models.ForeignKey(
        MealPlanDay, on_delete=models.CASCADE, related_name="entries", verbose_name="journée"
    )
    meal_type = models.ForeignKey(
        "diary.MealType",
        on_delete=models.CASCADE,
        related_name="meal_plan_entries",
        verbose_name="repas",
    )
    entry_type = models.CharField("type", max_length=16, choices=PlanEntryType.choices)
    food = models.ForeignKey(
        "nutrition.Food",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_plan_entries",
        verbose_name="aliment",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_plan_entries",
        verbose_name="recette",
    )
    saved_meal = models.ForeignKey(
        "recipes.SavedMeal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_plan_entries",
        verbose_name="repas enregistré",
    )
    quantity = models.DecimalField("quantité", max_digits=10, decimal_places=3)
    unit_label = models.CharField("unité", max_length=40)
    sort_order = models.PositiveIntegerField("ordre", default=0)
    generated_by_ai = models.BooleanField("proposé par IA", default=False)

    class Meta:
        verbose_name = "élément planifié"
        verbose_name_plural = "éléments planifiés"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="meal_plan_entry_positive_quantity"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_entry_type_display()} ({self.quantity})"
