"""Signaux de l'app comptes."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserProfile, UserSettings


@receiver(post_save, sender=User, dispatch_uid="accounts.create_user_related_objects")
def create_user_related_objects(sender, instance: User, created: bool, **kwargs) -> None:
    """Crée le profil et les paramètres à la création d'un utilisateur.

    Passer par un signal garantit que **tous** les chemins de création en
    bénéficient : acceptation d'une demande, `createsuperuser`, admin Django
    et tests.
    """
    if not created:
        return

    UserProfile.objects.get_or_create(user=instance)
    UserSettings.objects.get_or_create(user=instance)
