"""Accepte une demande d'inscription depuis la ligne de commande.

Utile à l'administrateur hors interface web, et utilisé par le parcours E2E
pour simuler la validation sans exposer d'endpoint de fixture.
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import RegistrationRequest, normalize_username
from accounts.services.registration import accept_registration_request


class Command(BaseCommand):
    help = "Accepte une demande d'inscription et crée le compte correspondant."

    def add_arguments(self, parser) -> None:
        parser.add_argument("username", help="Nom d'utilisateur de la demande à accepter.")

    def handle(self, *args, **options) -> None:
        username = options["username"]
        try:
            registration_request = RegistrationRequest.objects.get(
                normalized_username=normalize_username(username)
            )
        except RegistrationRequest.DoesNotExist as exc:
            raise CommandError(f"Aucune demande d'inscription pour « {username} ».") from exc

        try:
            user = accept_registration_request(registration_request)
        except ValidationError as exc:
            raise CommandError(str(exc.message if hasattr(exc, "message") else exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Compte « {user.username} » créé et activé."))
