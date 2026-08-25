"""Cycle de vie des demandes d'inscription (spec 01 §1, spec 02 §1)."""

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import RegistrationRequest, User, UserStatus, normalize_username
from notifications.services.email import (
    send_account_accepted_email,
    send_account_rejected_email,
)


def username_is_available(username: str, *, exclude_request_pk: int | None = None) -> bool:
    """Indique si un nom d'utilisateur est libre, sans tenir compte de la casse.

    Un username est indisponible s'il appartient déjà à un compte **ou** à une
    demande d'inscription en attente : sans cette seconde vérification, deux
    demandes concurrentes pourraient réserver le même nom.
    """
    normalized = normalize_username(username)
    if not normalized:
        return False

    if User.objects.filter(normalized_username=normalized).exists():
        return False

    pending = RegistrationRequest.objects.filter(normalized_username=normalized)
    if exclude_request_pk is not None:
        pending = pending.exclude(pk=exclude_request_pk)
    return not pending.exists()


class UsernameUnavailableError(ValidationError):
    """Le nom d'utilisateur a été pris entre la demande et son acceptation."""


@transaction.atomic
def accept_registration_request(registration_request: RegistrationRequest) -> User:
    """Crée le compte correspondant à une demande, puis supprime la demande.

    Le hash du mot de passe est transféré tel quel : l'utilisateur se connecte
    avec le mot de passe qu'il avait choisi, sans qu'un mot de passe en clair
    ait jamais été stocké ni transmis.

    L'ensemble est transactionnel et l'email n'est déclenché qu'après commit,
    afin qu'aucune notification ne parte si la création échoue.
    """
    if not username_is_available(
        registration_request.username, exclude_request_pk=registration_request.pk
    ):
        raise UsernameUnavailableError(
            f"Le nom d'utilisateur « {registration_request.username} » n'est plus disponible."
        )

    user = User(
        username=registration_request.username.strip(),
        email=registration_request.email or None,
        first_name=registration_request.first_name,
        last_name=registration_request.last_name,
        status=UserStatus.ACTIVE,
    )
    user.normalized_username = normalize_username(user.username)
    # Hash déjà calculé lors de la demande : `set_password` le ré-encoderait.
    user.password = registration_request.password
    user.full_clean(exclude=["password"])
    user.save()

    registration_request.delete()

    transaction.on_commit(lambda: send_account_accepted_email(user))
    return user


@transaction.atomic
def reject_registration_request(registration_request: RegistrationRequest) -> None:
    """Refuse une demande et la supprime.

    Aucun `User` n'est créé : le statut `REJECTED` n'a pas besoin d'exister
    (spec 05 §2). Une nouvelle demande reste possible plus tard.
    """
    recipient = registration_request.email
    first_name = registration_request.first_name

    registration_request.delete()

    transaction.on_commit(
        lambda: send_account_rejected_email(recipient=recipient, first_name=first_name)
    )
