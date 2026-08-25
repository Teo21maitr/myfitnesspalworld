"""Refuse une demande d'inscription depuis la ligne de commande."""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import RegistrationRequest, normalize_username
from accounts.services.registration import reject_registration_request


class Command(BaseCommand):
    help = "Refuse une demande d'inscription et la supprime."

    def add_arguments(self, parser) -> None:
        parser.add_argument("username", help="Nom d'utilisateur de la demande à refuser.")

    def handle(self, *args, **options) -> None:
        username = options["username"]
        try:
            registration_request = RegistrationRequest.objects.get(
                normalized_username=normalize_username(username)
            )
        except RegistrationRequest.DoesNotExist as exc:
            raise CommandError(f"Aucune demande d'inscription pour « {username} ».") from exc

        reject_registration_request(registration_request)
        self.stdout.write(self.style.SUCCESS(f"Demande « {username} » refusée et supprimée."))
