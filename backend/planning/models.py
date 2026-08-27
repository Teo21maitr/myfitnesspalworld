"""Liste de courses (spec 01 §16, spec 03 §8).

Le planner viendra dans la même app : prévoir ses repas et savoir quoi acheter
appartiennent au même domaine.

Une liste est un brouillon, pas un historique : elle se supprime franchement,
sans suppression douce, et rien ne la référence ensuite.
"""

from django.db import models
from django.db.models import Q


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
