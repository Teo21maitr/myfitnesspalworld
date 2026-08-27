"""Référentiel d'aliments (spec 01 §7 à §11, spec 03 §3).

Trois provenances cohabitent dans la même table : les aliments génériques
importés de Ciqual, les produits de marque mis en cache depuis Open Food
Facts, et les aliments créés par les utilisateurs. Le champ `source` les
distingue et pilote les permissions (spec 05 §6).

Une valeur nutritionnelle inconnue reste `NULL` : elle n'est jamais ramenée à
zéro (spec 01 §8).
"""

import unicodedata

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .nutrients import NutrientValues


class FoodSource(models.TextChoices):
    """Provenance de la fiche (spec 03 §3)."""

    CIQUAL = "ciqual", "Ciqual"
    OFF = "off", "Open Food Facts"
    USER = "user", "Utilisateur"
    GENERATED = "generated", "Généré"


class FoodVisibility(models.TextChoices):
    """Visibilité d'un aliment personnel (spec 01 §18).

    `SPECIFIC_USERS` désigne les comptes nommés par une `SharePermission` ;
    la visibilité seule ne dit pas qui, elle dit combien.
    """

    PRIVATE = "private", "Privé"
    SPECIFIC_USERS = "specific_users", "Utilisateurs choisis"
    APP_USERS = "app_users", "Tous les utilisateurs actifs"


class UnitType(models.TextChoices):
    """Unité de référence d'un aliment."""

    GRAM = "g", "Grammes"
    MILLILITER = "ml", "Millilitres"
    UNIT = "unit", "Unité"


def normalize_search_text(*parts: str | None) -> str:
    """Forme désaccentuée et minuscule utilisée par la recherche.

    La normalisation est faite à l'écriture plutôt qu'à chaque requête : elle
    permet d'indexer directement le texte et rend la recherche insensible à la
    casse comme aux accents (spec 01 §7).
    """
    joined = " ".join(part.strip() for part in parts if part)
    decomposed = unicodedata.normalize("NFKD", joined)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_accents.lower().split())


class FoodQuerySet(models.QuerySet):
    """Filtres de visibilité, appliqués en base et jamais dans la vue."""

    def active(self):
        return self.filter(is_active=True, deleted_at__isnull=True)

    def visible_to(self, user):
        """Aliments qu'un utilisateur a le droit de consulter (spec 05 §6)."""
        # Import tardif : `social` dépend des apps métier pour résoudre une
        # ressource, et l'importer au chargement des modèles créerait un cycle.
        from social.models import ResourceType
        from social.services.sharing import active_owner, shared_resource_ids

        return self.active().filter(
            # Sources globales : lisibles par tout compte actif.
            Q(source__in=[FoodSource.CIQUAL, FoodSource.OFF])
            # Ses propres aliments, quelle que soit leur visibilité.
            | Q(owner=user)
            # Ceux que d'autres ont ouverts à tous les comptes actifs — sauf
            # si leur propriétaire a été suspendu (spec 05 §2).
            | (Q(visibility=FoodVisibility.APP_USERS) & active_owner())
            # Ceux qu'on lui a partagés nommément.
            | Q(pk__in=shared_resource_ids(user, ResourceType.FOOD))
        )

    def editable_by(self, user):
        """Aliments qu'un utilisateur peut modifier : uniquement les siens."""
        return self.active().filter(owner=user, source=FoodSource.USER)


class Food(models.Model):
    """Fiche d'un aliment."""

    name = models.CharField("nom", max_length=255)
    brand = models.CharField("marque", max_length=255, blank=True, default="")
    barcode = models.CharField(  # noqa: DJ001 - nul quand le produit n'en a pas
        "code-barres", max_length=32, null=True, blank=True, db_index=True
    )
    source = models.CharField("source", max_length=16, choices=FoodSource.choices, db_index=True)
    visibility = models.CharField(
        "visibilité",
        max_length=16,
        choices=FoodVisibility.choices,
        default=FoodVisibility.PRIVATE,
    )
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="foods",
        verbose_name="propriétaire",
        help_text="Obligatoire pour un aliment créé par un utilisateur.",
    )
    external_id = models.CharField(  # noqa: DJ001 - nul pour un aliment personnel
        "identifiant externe",
        max_length=64,
        null=True,
        blank=True,
        help_text="Code Ciqual ou identifiant Open Food Facts.",
    )
    default_unit_type = models.CharField(
        "type d'unité", max_length=8, choices=UnitType.choices, default=UnitType.GRAM
    )
    # Les valeurs nutritionnelles sont toujours exprimées pour cette quantité.
    reference_amount = models.DecimalField(
        "quantité de référence", max_digits=7, decimal_places=2, default=100
    )
    reference_unit = models.CharField(
        "unité de référence", max_length=8, choices=UnitType.choices, default=UnitType.GRAM
    )
    is_verified = models.BooleanField("vérifié", default=False)
    is_active = models.BooleanField("actif", default=True)
    search_text = models.TextField("texte de recherche", editable=False, default="")
    external_updated_at = models.DateTimeField("mis à jour à la source le", null=True, blank=True)
    cache_refreshed_at = models.DateTimeField("cache rafraîchi le", null=True, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)
    deleted_at = models.DateTimeField(
        "supprimé le",
        null=True,
        blank=True,
        help_text="Suppression douce : les entrées de journal historiques restent valides.",
    )

    objects = FoodQuerySet.as_manager()

    class Meta:
        verbose_name = "aliment"
        verbose_name_plural = "aliments"
        ordering = ["name"]
        constraints = [
            # Une source externe ne peut pas référencer deux fois le même
            # identifiant : c'est la clé d'idempotence des imports.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=Q(external_id__isnull=False),
                name="food_unique_external_id_per_source",
            ),
            models.CheckConstraint(
                condition=~Q(source=FoodSource.USER) | Q(owner__isnull=False),
                name="food_user_source_requires_owner",
            ),
            models.CheckConstraint(
                condition=Q(reference_amount__gt=0), name="food_reference_amount_positive"
            ),
        ]
        indexes = [
            # Index trigramme : c'est lui qui rend la recherche tolérante aux
            # fautes et instantanée (spec 01 §7, spec 10 §4).
            GinIndex(
                fields=["search_text"],
                name="food_search_text_trgm",
                opclasses=["gin_trgm_ops"],
            ),
            models.Index(Lower("name"), name="food_name_lower"),
            models.Index(fields=["owner", "-updated_at"], name="food_owner_updated"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.brand})" if self.brand else self.name

    def save(self, *args, **kwargs):
        self.search_text = normalize_search_text(self.name, self.brand)
        super().save(*args, **kwargs)

    @property
    def is_editable_by_owner(self) -> bool:
        """Seuls les aliments personnels sont modifiables (spec 01 §8)."""
        return self.source == FoodSource.USER

    @property
    def display_source(self) -> str:
        return self.get_source_display()


class FoodNutrition(NutrientValues):
    """Valeurs nutritionnelles pour la quantité de référence de l'aliment.

    Les champs viennent de `NutrientValues`, partagé avec la recette : le
    journal recopie l'un ou l'autre dans le même jeu de colonnes de snapshot,
    et deux listes séparées finiraient par diverger.
    """

    food = models.OneToOneField(
        Food, on_delete=models.CASCADE, related_name="nutrition", verbose_name="aliment"
    )

    class Meta:
        verbose_name = "valeurs nutritionnelles"
        verbose_name_plural = "valeurs nutritionnelles"

    def __str__(self) -> str:
        return f"Nutrition de {self.food.name}"


class FoodPortion(models.Model):
    """Portion nommée d'un aliment (spec 01 §9).

    Une portion posée par un utilisateur sur un aliment global lui reste
    privée : `owner` non nul signifie « visible par ce seul utilisateur ».

    Aucune équivalence n'est déduite : sans densité connue, on ne convertit
    jamais des millilitres en grammes.
    """

    food = models.ForeignKey(
        Food, on_delete=models.CASCADE, related_name="portions", verbose_name="aliment"
    )
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="food_portions",
        verbose_name="propriétaire",
        help_text="Nul pour une portion officielle, sinon portion privée à cet utilisateur.",
    )
    name = models.CharField("nom", max_length=100)
    gram_equivalent = models.DecimalField(
        "équivalent en grammes", max_digits=9, decimal_places=3, null=True, blank=True
    )
    milliliter_equivalent = models.DecimalField(
        "équivalent en millilitres", max_digits=9, decimal_places=3, null=True, blank=True
    )
    unit_equivalent = models.DecimalField(
        "équivalent en unités", max_digits=9, decimal_places=3, null=True, blank=True
    )
    is_default = models.BooleanField("portion par défaut", default=False)
    sort_order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "portion"
        verbose_name_plural = "portions"
        ordering = ["sort_order", "name"]
        constraints = [
            # `nulls_distinct=False` est indispensable : sans lui, deux
            # portions officielles homonymes (owner NULL) passeraient, puisque
            # SQL considère deux NULL comme distincts.
            models.UniqueConstraint(
                fields=["food", "owner", "name"],
                name="food_portion_unique_name",
                nulls_distinct=False,
            ),
            # Une portion sans aucune équivalence ne veut rien dire.
            models.CheckConstraint(
                condition=Q(gram_equivalent__isnull=False)
                | Q(milliliter_equivalent__isnull=False)
                | Q(unit_equivalent__isnull=False),
                name="food_portion_requires_equivalent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} — {self.food.name}"


class UserFoodFavorite(models.Model):
    """Étoile posée manuellement par l'utilisateur (spec 01 §7)."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="food_favorites",
        verbose_name="utilisateur",
    )
    food = models.ForeignKey(
        Food, on_delete=models.CASCADE, related_name="favorited_by", verbose_name="aliment"
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "aliment favori"
        verbose_name_plural = "aliments favoris"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "food"], name="user_food_favorite_unique")
        ]

    def __str__(self) -> str:
        return f"{self.user.username} ★ {self.food.name}"


class UserFoodHistory(models.Model):
    """Usage d'un aliment par un utilisateur.

    Alimente les listes « récents » et « fréquents », ainsi que le classement
    de la recherche (spec 01 §7).
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="food_history",
        verbose_name="utilisateur",
    )
    food = models.ForeignKey(
        Food, on_delete=models.CASCADE, related_name="usage_history", verbose_name="aliment"
    )
    last_used_at = models.DateTimeField("dernière utilisation")
    use_count = models.PositiveIntegerField("nombre d'utilisations", default=1)

    class Meta:
        verbose_name = "historique d'aliment"
        verbose_name_plural = "historiques d'aliments"
        ordering = ["-last_used_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "food"], name="user_food_history_unique")
        ]
        indexes = [
            models.Index(fields=["user", "-last_used_at"], name="food_history_recent"),
            models.Index(fields=["user", "-use_count"], name="food_history_frequent"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} — {self.food.name} ({self.use_count})"
