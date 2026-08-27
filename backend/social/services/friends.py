"""Demandes d'amitié et amitiés (spec 01 §17)."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from accounts.models import User, UserStatus
from social.models import FriendRequest, FriendRequestStatus, Friendship
from social.services.sharing import are_friends, canonical_pair, revoke_between


def friends_of(user: User):
    """Comptes actifs amis de `user`."""
    friendships = Friendship.objects.filter(Q(user_1=user) | Q(user_2=user))
    ids = {
        friendship.user_2_id if friendship.user_1_id == user.id else friendship.user_1_id
        for friendship in friendships
    }
    return User.objects.filter(pk__in=ids, status=UserStatus.ACTIVE).order_by("username")


@transaction.atomic
def send_request(*, from_user: User, to_user: User) -> FriendRequest:
    """Crée une demande, après avoir écarté les cas qui n'en sont pas."""
    if from_user.id == to_user.id:
        raise ValidationError({"to_user_id": "Vous ne pouvez pas vous ajouter vous-même."})

    if to_user.status != UserStatus.ACTIVE:
        raise ValidationError({"to_user_id": "Ce compte n'est pas disponible."})

    if are_friends(from_user, to_user):
        raise ValidationError({"to_user_id": "Vous êtes déjà amis."})

    pending = (
        FriendRequest.objects.filter(status=FriendRequestStatus.PENDING)
        .filter(Q(from_user=from_user, to_user=to_user) | Q(from_user=to_user, to_user=from_user))
        .first()
    )

    if pending is not None:
        # Une demande croisée vaut acceptation : réémettre en sens inverse
        # signifie qu'on veut la même chose que l'autre.
        if pending.from_user_id == to_user.id:
            accept(request=pending, user=from_user)
            return pending
        raise ValidationError({"to_user_id": "Une demande est déjà en attente."})

    return FriendRequest.objects.create(from_user=from_user, to_user=to_user)


@transaction.atomic
def accept(*, request: FriendRequest, user: User) -> Friendship:
    """Accepte une demande reçue. L'émetteur ne peut pas accepter la sienne."""
    if request.to_user_id != user.id:
        raise ValidationError("Cette demande ne vous est pas adressée.")

    if request.status != FriendRequestStatus.PENDING:
        raise ValidationError("Cette demande a déjà été traitée.")

    request.status = FriendRequestStatus.ACCEPTED
    request.save(update_fields=["status", "updated_at"])

    low, high = canonical_pair(request.from_user, request.to_user)
    friendship, _ = Friendship.objects.get_or_create(user_1=low, user_2=high)
    return friendship


@transaction.atomic
def reject(*, request: FriendRequest, user: User) -> FriendRequest:
    if request.to_user_id != user.id:
        raise ValidationError("Cette demande ne vous est pas adressée.")

    if request.status != FriendRequestStatus.PENDING:
        raise ValidationError("Cette demande a déjà été traitée.")

    request.status = FriendRequestStatus.REJECTED
    request.save(update_fields=["status", "updated_at"])
    return request


@transaction.atomic
def remove_friend(*, user: User, other: User) -> None:
    """Retire un ami **et** révoque les partages qui le visaient.

    Les deux opérations ne se séparent pas : effacer l'amitié en laissant les
    permissions laisserait l'ancien ami lire le journal comme avant, sans que
    rien ne le signale (spec 01 §17).
    """
    low, high = canonical_pair(user, other)
    deleted, _ = Friendship.objects.filter(user_1=low, user_2=high).delete()

    if deleted == 0:
        raise ValidationError("Vous n'êtes pas amis.")

    revoke_between(user, other)


def search_users(*, user: User, query: str):
    """Recherche partielle par nom d'utilisateur (spec 01 §17).

    Ne porte **jamais** sur l'email : la spec 01 §1 l'exclut explicitement de
    la recherche sociale.
    """
    term = (query or "").strip()
    if len(term) < 2:
        return User.objects.none()

    return (
        User.objects.filter(status=UserStatus.ACTIVE, normalized_username__contains=term.casefold())
        .exclude(pk=user.pk)
        .order_by("username")
    )
