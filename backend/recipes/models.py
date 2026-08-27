"""Recettes et repas enregistrés (spec 01 §13 et §14, spec 03 §5 et §6).

Une **recette** rassemble des ingrédients préparés ensemble, puis divisés en
portions : sa nutrition est mise en cache pour une portion, ce qui permet de la
journaliser sans recharger ses ingrédients.

Un **repas enregistré** est un raccourci : un ensemble d'aliments et de recettes
déjà portionnés, qui se déplie en entrées de journal normales et indépendantes.

Les deux vivent dans la même app : la spec 00 §6 n'en prévoit pas d'autre.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from nutrition.models.nutrients import NutrientValues


class RecipeVisibility(models.TextChoices):
    """Visibilité d'une recette ou d'un repas enregistré (spec 01 §18).

    Reprend les valeurs de `FoodVisibility` sans la réutiliser : partager
    l'énumération imposerait un `AlterField` sur une table déjà en production
    pour un gain purement cosmétique.

    `SPECIFIC_USERS` existe dans le modèle mais n'est pas encore applicable :
    il dépend de `SharePermission`, qui arrivera avec le partage.
    """

    PRIVATE = "private", "Privé"
    SPECIFIC_USERS = "specific_users", "Utilisateurs choisis"
    APP_USERS = "app_users", "Tous les utilisateurs actifs"


class ItemType(models.TextChoices):
    """Nature d'un élément de repas enregistré (spec 03 §5)."""

    FOOD = "food", "Aliment"
    RECIPE = "recipe", "Recette"


class OwnedQuerySet(models.QuerySet):
    """Filtres de visibilité communs aux recettes et aux repas enregistrés."""

    def active(self):
        return self.filter(deleted_at__isnull=True)

    def visible_to(self, user):
        """Ce qu'un utilisateur a le droit de consulter (spec 05 §7)."""
        return self.active().filter(Q(owner=user) | Q(visibility=RecipeVisibility.APP_USERS))

    def editable_by(self, user):
        """Ce qu'un utilisateur peut modifier : uniquement ce qui lui appartient."""
        return self.active().filter(owner=user)


class Recipe(models.Model):
    """Recette d'un utilisateur.

    Suppression douce : les entrées de journal la référencent, et modifier ou
    supprimer une recette ne doit jamais toucher l'historique (spec 01 §14).
    """

    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="propriétaire",
    )
    name = models.CharField("nom", max_length=255)
    description = models.CharField("description", max_length=500, blank=True, default="")
    instructions = models.TextField("instructions", blank=True, default="")
    servings = models.DecimalField(
        "nombre de portions",
        max_digits=6,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0)],
    )
    visibility = models.CharField(
        "visibilité",
        max_length=16,
        choices=RecipeVisibility.choices,
        default=RecipeVisibility.PRIVATE,
    )
    is_favorite = models.BooleanField("favori", default=False)
    deleted_at = models.DateTimeField(
        "supprimée le",
        null=True,
        blank=True,
        help_text="Suppression douce : les entrées de journal historiques restent valides.",
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        verbose_name = "recette"
        verbose_name_plural = "recettes"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(servings__gt=0), name="recipe_positive_servings"),
        ]
        indexes = [models.Index(fields=["owner", "name"], name="recipe_owner_name")]

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(models.Model):
    """Aliment entrant dans une recette.

    Un ingrédient est un aliment, jamais une autre recette : la spec 03 §6 ne
    prévoit pas d'imbrication, qui poserait la question des cycles.

    `SET_NULL` plutôt que `CASCADE` : supprimer le compte qui possédait un
    aliment partagé ne doit pas faire disparaître silencieusement un ingrédient
    d'une recette qui ne lui appartient pas. La ligne subsiste, son nom est
    conservé, et la nutrition de la recette devient partielle — signalée, plutôt
    que fausse sans le dire.
    """

    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="ingredients", verbose_name="recette"
    )
    food = models.ForeignKey(
        "nutrition.Food",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipe_ingredients",
        verbose_name="aliment",
    )
    food_name = models.CharField(
        "nom de l'aliment",
        max_length=255,
        help_text="Recopié à l'ajout : l'ingrédient reste lisible si l'aliment disparaît.",
    )
    quantity = models.DecimalField("quantité", max_digits=10, decimal_places=3)
    unit_label = models.CharField("unité", max_length=40)
    sort_order = models.PositiveIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "ingrédient"
        verbose_name_plural = "ingrédients"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="recipe_ingredient_positive_quantity"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} {self.unit_label} de {self.food_name}"


class RecipeNutrition(NutrientValues):
    """Valeurs nutritionnelles **pour une portion**.

    Le cache porte les vingt nutriments et non les seules macros de la
    spec 03 §6 : le snapshot du journal les exige tous, et un cache partiel
    obligerait à recharger les ingrédients au moment de journaliser.

    Par portion plutôt que pour la recette entière : c'est ce qui s'affiche et
    ce qui se recopie dans une entrée.
    """

    recipe = models.OneToOneField(
        Recipe, on_delete=models.CASCADE, related_name="nutrition", verbose_name="recette"
    )
    incomplete_nutrients = models.JSONField(
        "nutriments partiels",
        default=list,
        blank=True,
        help_text="Nutriments qu'au moins un ingrédient ne renseigne pas (spec 01 §8).",
    )
    computed_at = models.DateTimeField("calculé le", auto_now=True)

    class Meta:
        verbose_name = "valeurs nutritionnelles d'une recette"
        verbose_name_plural = "valeurs nutritionnelles des recettes"

    def __str__(self) -> str:
        return f"Nutrition de {self.recipe.name}"


class SavedMeal(models.Model):
    """Ensemble réutilisable d'aliments et de recettes déjà portionnés (spec 01 §13)."""

    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="saved_meals",
        verbose_name="propriétaire",
    )
    name = models.CharField("nom", max_length=255)
    description = models.CharField("description", max_length=500, blank=True, default="")
    visibility = models.CharField(
        "visibilité",
        max_length=16,
        choices=RecipeVisibility.choices,
        default=RecipeVisibility.PRIVATE,
    )
    deleted_at = models.DateTimeField("supprimé le", null=True, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        verbose_name = "repas enregistré"
        verbose_name_plural = "repas enregistrés"
        ordering = ["name"]
        indexes = [models.Index(fields=["owner", "name"], name="saved_meal_owner_name")]

    def __str__(self) -> str:
        return self.name


class SavedMealItem(models.Model):
    """Élément d'un repas enregistré : un aliment ou une recette portionné.

    Les deux clés sont en `SET_NULL` pour la même raison que l'ingrédient : un
    élément dont la source a disparu reste visible et nommé, au lieu de
    s'évaporer du repas sans prévenir.
    """

    saved_meal = models.ForeignKey(
        SavedMeal, on_delete=models.CASCADE, related_name="items", verbose_name="repas"
    )
    item_type = models.CharField("type", max_length=16, choices=ItemType.choices)
    food = models.ForeignKey(
        "nutrition.Food",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_meal_items",
        verbose_name="aliment",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_meal_items",
        verbose_name="recette",
    )
    item_name = models.CharField(
        "nom",
        max_length=255,
        help_text="Recopié à l'ajout : l'élément reste lisible si sa source disparaît.",
    )
    quantity = models.DecimalField("quantité", max_digits=10, decimal_places=3)
    unit_label = models.CharField("unité", max_length=40)
    sort_order = models.PositiveIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "élément de repas"
        verbose_name_plural = "éléments de repas"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="saved_meal_item_positive_quantity"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} {self.unit_label} de {self.item_name}"
