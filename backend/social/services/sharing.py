"""Ce qu'un utilisateur a le droit de lire chez un autre (spec 01 §18, spec 05).

Toutes les erreurs de ce domaine se ressemblent : un accès accordé légitimement,
puis conservé après la disparition de ce qui le justifiait. Aucune ne lève
d'exception, aucune ne se voit à l'écran, et chacune est une fuite de données
privées. Les règles vivent donc ici, en un seul endroit, plutôt que dispersées
dans les vues.
"""

from django.db import transaction
from django.db.models import Q

from accounts.models import User, UserStatus
from social.models import (
    IDENTIFIED_RESOURCES,
    Friendship,
    ResourceType,
    SharePermission,
    VisibilityType,
)


def canonical_pair(first: User, second: User) -> tuple[User, User]:
    """Couple ordonné par identifiant croissant.

    L'amitié est bidirectionnelle : la stocker sous une forme unique évite que
    A→B et B→A coexistent, auquel cas « sommes-nous amis ? » n'aurait pas de
    réponse unique.
    """
    return (first, second) if first.id < second.id else (second, first)


def are_friends(first: User, second: User) -> bool:
    if first.id == second.id:
        return False

    low, high = canonical_pair(first, second)
    return Friendship.objects.filter(user_1=low, user_2=high).exists()


def active_owner(prefix: str = "owner") -> Q:
    """Le propriétaire est actif, ou la ressource n'en a pas.

    La spec 05 §2 rend inaccessibles les partages d'un compte suspendu.
    `IsActiveAccount` ne contrôle que l'appelant : sans cette clause, les
    ressources d'un compte suspendu resteraient lisibles par ses amis.
    """
    return Q(**{f"{prefix}__isnull": True}) | Q(**{f"{prefix}__status": UserStatus.ACTIVE})


def shared_resource_ids(user: User, resource_type: str):
    """Identifiants d'un type que `user` peut lire par partage.

    Les **deux** portées comptent : un partage nommé sur lui, et un partage
    ouvert à tous les comptes actifs. Ne retenir que le premier laissait le
    second sans effet — la ressource restait invisible bien que le partage
    existe, puisque rien ne touchait sa colonne `visibility`.

    Renvoie une sous-requête, pour que les filtres de visibilité restent une
    seule requête. Le **type** fait partie du filtre : les identifiants sont
    propres à chaque table, et n'interroger que `resource_id` transformerait un
    partage de recette en accès à un aliment portant le même numéro.
    """
    return (
        SharePermission.objects.filter(
            resource_type=resource_type,
            owner__status=UserStatus.ACTIVE,
        )
        .filter(
            Q(target_user=user, visibility_type=VisibilityType.SPECIFIC_USER)
            | Q(visibility_type=VisibilityType.APP_USERS)
        )
        .values("resource_id")
    )


def can_read(user: User, owner: User, resource_type: str, resource_id: int | None = None) -> bool:
    """Autorisation de lecture, pour les ressources sans liste à filtrer.

    Le journal et la progression ne sont pas des lignes : on ne peut pas les
    restreindre par un `pk__in`, il faut poser la question directement.
    """
    if owner.status != UserStatus.ACTIVE:
        return False

    if user.id == owner.id:
        return True

    return (
        SharePermission.objects.filter(
            owner=owner,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        .filter(
            Q(target_user=user, visibility_type=VisibilityType.SPECIFIC_USER)
            | Q(visibility_type=VisibilityType.APP_USERS)
        )
        .exists()
    )


@transaction.atomic
def revoke_resource(resource_type: str, resource_id: int) -> int:
    """Retire tous les partages d'une ressource redevenue privée.

    Sans cela, « privé » ne voudrait rien dire : la colonne `visibility` de la
    ressource et les permissions sont indépendantes, et l'une pourrait annoncer
    « personne » pendant que les autres laissent lire. C'est la direction où
    l'erreur coûte le plus cher.
    """
    deleted, _ = SharePermission.objects.filter(
        resource_type=resource_type, resource_id=resource_id
    ).delete()

    return deleted


@transaction.atomic
def revoke_between(first: User, second: User) -> int:
    """Supprime les partages ciblés entre deux comptes, dans les deux sens.

    Appelée au retrait d'ami (spec 01 §17). Les partages `app_users` survivent :
    ils ne visaient personne en particulier, et l'amitié n'était pas leur
    fondement.
    """
    deleted, _ = (
        SharePermission.objects.filter(visibility_type=VisibilityType.SPECIFIC_USER)
        .filter(Q(owner=first, target_user=second) | Q(owner=second, target_user=first))
        .delete()
    )

    return deleted


def sync_visibility(user: User, resource_type: str, resource_id: int) -> None:
    """Recalcule la colonne `visibility` d'après les partages qui subsistent.

    Les deux disent la même chose sous deux formes : la colonne résume la
    portée, les permissions nomment les destinataires. La colonne est donc
    **dérivée**, jamais posée d'après une intention ponctuelle — sinon révoquer
    un partage la laisserait annoncer « ouvert à tous » alors que plus rien ne
    l'est.
    """
    from nutrition.models import FoodVisibility
    from recipes.models import RecipeVisibility

    resource = resolve_owned_resource(user, resource_type, resource_id)
    if resource is None:
        return

    remaining = SharePermission.objects.filter(
        owner=user, resource_type=resource_type, resource_id=resource_id
    )
    choices = FoodVisibility if resource_type == ResourceType.FOOD else RecipeVisibility

    if remaining.filter(visibility_type=VisibilityType.APP_USERS).exists():
        wanted = choices.APP_USERS
    elif remaining.exists():
        wanted = choices.SPECIFIC_USERS
    else:
        wanted = choices.PRIVATE

    if resource.visibility != wanted:
        resource.visibility = wanted
        resource.save(update_fields=["visibility", "updated_at"])


def requires_resource_id(resource_type: str) -> bool:
    """Le journal et la progression désignent leur propriétaire, pas une ligne."""
    return resource_type in IDENTIFIED_RESOURCES


#: Résolution d'une ressource identifiée vers son propriétaire, pour vérifier
#: qu'on ne partage que ce qui nous appartient. Importée tardivement : `social`
#: ne doit pas dépendre des apps métier au chargement.
def resolve_owned_resource(user: User, resource_type: str, resource_id: int):
    """Ressource de ce type appartenant à l'appelant, ou `None`."""
    from nutrition.models import Food, FoodSource
    from recipes.models import Recipe, SavedMeal

    if resource_type == ResourceType.FOOD:
        return Food.objects.filter(
            pk=resource_id, owner=user, source=FoodSource.USER, deleted_at__isnull=True
        ).first()

    if resource_type == ResourceType.RECIPE:
        return Recipe.objects.editable_by(user).filter(pk=resource_id).first()

    if resource_type == ResourceType.SAVED_MEAL:
        return SavedMeal.objects.editable_by(user).filter(pk=resource_id).first()

    return None


def describe(permissions) -> dict[tuple[str, int | None], str]:
    """Nom lisible de chaque ressource partagée, en une requête par type.

    Résoudre ligne à ligne suffirait à l'affichage mais ferait une requête par
    partage : le regroupement par type en fait trois au plus.
    """
    from nutrition.models import Food
    from recipes.models import Recipe, SavedMeal

    wanted: dict[str, set[int]] = {}
    for permission in permissions:
        if permission.resource_id is not None:
            wanted.setdefault(permission.resource_type, set()).add(permission.resource_id)

    models = {
        ResourceType.FOOD: Food,
        ResourceType.RECIPE: Recipe,
        ResourceType.SAVED_MEAL: SavedMeal,
    }

    names: dict[tuple[str, int | None], str] = {}
    for resource_type, ids in wanted.items():
        model = models.get(resource_type)
        if model is None:
            continue
        for pk, name in model.objects.filter(pk__in=ids).values_list("pk", "name"):
            names[(resource_type, pk)] = name

    return names
