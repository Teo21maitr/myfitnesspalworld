"""Amitiés et partages (spec 01 §17 et §18, spec 03 §9).

Le partage à des utilisateurs précis suppose une relation d'amitié : la
spec 01 §17 les lie en rendant le retrait d'ami révocateur des partages qui le
visaient. Une permission ne survit donc jamais à la relation qui la justifiait.
"""

from django.db import models
from django.db.models import Q


class FriendRequestStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée"
    REJECTED = "rejected", "Refusée"
    CANCELLED = "cancelled", "Annulée"


class ResourceType(models.TextChoices):
    """Ressources partageables (spec 01 §18).

    Les photos de progression n'y figurent pas et ne doivent jamais y figurer :
    elles ne sont partageables sous aucune forme (spec 01 §20).
    """

    FOOD = "food", "Aliment personnel"
    RECIPE = "recipe", "Recette"
    SAVED_MEAL = "saved_meal", "Repas enregistré"
    DIARY = "diary", "Journal"
    PROGRESS = "progress", "Progression"


#: Ressources désignées par un identifiant. Le journal et la progression n'en
#: ont pas : ils désignent l'ensemble des données de leur propriétaire.
IDENTIFIED_RESOURCES = frozenset({ResourceType.FOOD, ResourceType.RECIPE, ResourceType.SAVED_MEAL})


class VisibilityType(models.TextChoices):
    SPECIFIC_USER = "specific_user", "Utilisateur choisi"
    APP_USERS = "app_users", "Tous les utilisateurs actifs"


class FriendRequest(models.Model):
    """Demande d'amitié (spec 01 §17)."""

    from_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="sent_friend_requests",
        verbose_name="demandeur",
    )
    to_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="received_friend_requests",
        verbose_name="destinataire",
    )
    status = models.CharField(
        "statut",
        max_length=16,
        choices=FriendRequestStatus.choices,
        default=FriendRequestStatus.PENDING,
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)

    class Meta:
        verbose_name = "demande d'amitié"
        verbose_name_plural = "demandes d'amitié"
        ordering = ["-created_at"]
        constraints = [
            # Une seule demande en attente par couple orienté : réémettre ne
            # doit pas empiler des lignes que l'un et l'autre verraient.
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                condition=Q(status=FriendRequestStatus.PENDING),
                name="friend_request_unique_pending",
            ),
            models.CheckConstraint(
                condition=~Q(from_user=models.F("to_user")),
                name="friend_request_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"], name="friend_request_inbox"),
            models.Index(fields=["from_user", "status"], name="friend_request_outbox"),
        ]

    def __str__(self) -> str:
        return f"{self.from_user} → {self.to_user} ({self.status})"


class Friendship(models.Model):
    """Amitié, bidirectionnelle par nature (spec 01 §17).

    Le couple est stocké sous forme canonique — le plus petit identifiant en
    `user_1` — et l'unicité porte dessus. Sans cela, A→B et B→A pourraient
    coexister et « sommes-nous amis ? » n'aurait pas de réponse unique.
    """

    user_1 = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="friendships_as_first",
        verbose_name="premier",
    )
    user_2 = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="friendships_as_second",
        verbose_name="second",
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "amitié"
        verbose_name_plural = "amitiés"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user_1", "user_2"], name="friendship_unique_pair"),
            models.CheckConstraint(
                condition=Q(user_1__lt=models.F("user_2")),
                name="friendship_canonical_order",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_1} ↔ {self.user_2}"


class SharePermission(models.Model):
    """Autorisation de lecture sur une ressource (spec 01 §18, spec 03 §9).

    `resource_id` est nul pour le journal et la progression : ils ne sont pas
    une ligne mais l'ensemble des données de leur propriétaire (spec 05 §8).

    Le couple `(resource_type, resource_id)` forme la clé de lecture. Les
    identifiants sont propres à chaque table : la recette 42 et l'aliment 42
    coexistent, et interroger le seul identifiant transformerait un partage de
    recette en accès à un aliment.
    """

    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="shares_granted",
        verbose_name="propriétaire",
    )
    target_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="shares_received",
        verbose_name="destinataire",
        help_text="Nul pour un partage à tous les comptes actifs.",
    )
    resource_type = models.CharField("ressource", max_length=16, choices=ResourceType.choices)
    resource_id = models.PositiveBigIntegerField(
        "identifiant de la ressource",
        null=True,
        blank=True,
        help_text="Nul pour le journal et la progression, qui n'en ont pas.",
    )
    visibility_type = models.CharField("portée", max_length=16, choices=VisibilityType.choices)
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "partage"
        verbose_name_plural = "partages"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "target_user", "resource_type", "resource_id"],
                name="share_unique_target",
            ),
            # Un partage ciblé nomme quelqu'un ; un partage global ne nomme
            # personne. L'inverse, dans un cas comme dans l'autre, n'a pas de
            # sens et ouvrirait un accès mal défini.
            models.CheckConstraint(
                condition=(
                    Q(visibility_type=VisibilityType.SPECIFIC_USER, target_user__isnull=False)
                    | Q(visibility_type=VisibilityType.APP_USERS, target_user__isnull=True)
                ),
                name="share_target_matches_visibility",
            ),
            models.CheckConstraint(
                condition=~Q(owner=models.F("target_user")),
                name="share_not_to_self",
            ),
        ]
        indexes = [
            models.Index(fields=["target_user", "resource_type"], name="share_received_by_type"),
            models.Index(fields=["owner", "resource_type"], name="share_granted_by_type"),
        ]

    def __str__(self) -> str:
        target = self.target_user or "tous les comptes actifs"
        return f"{self.owner} partage {self.resource_type} avec {target}"
