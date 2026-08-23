"""Permissions transverses (spec 05)."""

from rest_framework.permissions import BasePermission

from accounts.models import UserStatus


class IsActiveAccount(BasePermission):
    """N'autorise que les comptes au statut ACTIVE.

    Un compte PENDING ou SUSPENDED est authentifié au sens technique mais ne
    doit accéder à aucune fonction métier (spec 05 §2).
    """

    message = "Votre compte n'est pas actif."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(
            user and user.is_authenticated and getattr(user, "status", None) == UserStatus.ACTIVE
        )
