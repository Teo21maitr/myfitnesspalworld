"""Envoi et journalisation des emails (spec 05 §4 et §15).

Ce dossier était **vide** alors que trois emails transactionnels partent en
production depuis l'étape 2. Les règles qu'ils appliquent — un destinataire
absent n'est pas une erreur, un échec ne fait jamais tomber l'action métier, et
la trace ne contient jamais le contenu — n'étaient vérifiées qu'indirectement,
depuis `accounts`.
"""

import pytest

from accounts.models import User, UserStatus
from notifications.models import EmailLog, EmailStatus, EmailType
from notifications.services import email as email_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def with_email(db) -> User:
    return User.objects.create_user(
        username="teo",
        password="un-mot-de-passe-solide-1",
        email="teo@example.com",
        first_name="Téo",
        status=UserStatus.ACTIVE,
    )


@pytest.fixture
def without_email(db) -> User:
    return User.objects.create_user(
        username="sans-email", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


class TestSending:
    def test_un_email_part_et_laisse_une_trace(self, with_email, mailoutbox):
        log = email_service.send_account_accepted_email(with_email)

        assert len(mailoutbox) == 1
        assert log.status == EmailStatus.SENT
        assert log.email_type == EmailType.ACCOUNT_ACCEPTED
        assert log.recipient == "teo@example.com"

    def test_le_message_a_une_version_texte_et_html(self, with_email, mailoutbox):
        """Un client qui n'affiche pas le HTML doit rester servi."""
        email_service.send_account_accepted_email(with_email)

        message = mailoutbox[0]
        assert message.body
        assert message.alternatives
        assert message.alternatives[0][1] == "text/html"

    def test_sans_destinataire_rien_ne_part_et_ce_n_est_pas_une_erreur(
        self, without_email, mailoutbox
    ):
        """L'email est facultatif dans ce projet (spec 01 §1)."""
        log = email_service.send_account_accepted_email(without_email)

        assert log is None
        assert mailoutbox == []
        assert not EmailLog.objects.exists()

    def test_un_refus_se_journalise_sans_compte(self, mailoutbox):
        """La demande refusée est supprimée : il ne reste aucun `User`."""
        log = email_service.send_account_rejected_email(
            recipient="candidat@example.com", first_name="Alex"
        )

        assert log.user is None
        assert log.status == EmailStatus.SENT

    def test_le_lien_de_reinitialisation_n_est_jamais_journalise(self, with_email, mailoutbox):
        """Un token dans la trace serait un token lisible par l'admin."""
        secret = "https://app.example/reinitialiser?token=un-secret-tres-identifiable"

        log = email_service.send_password_reset_email(with_email, secret)

        assert secret in mailoutbox[0].body
        assert secret not in str(log.__dict__)
        assert log.provider_response_summary is None


class TestFailures:
    def test_un_echec_ne_leve_pas_et_se_journalise(self, with_email, monkeypatch, mailoutbox):
        """L'action métier qui l'a déclenché ne doit jamais tomber avec lui."""

        def boom(self, *args, **kwargs):
            raise ConnectionRefusedError("le serveur SMTP est absent")

        monkeypatch.setattr(
            "django.core.mail.message.EmailMultiAlternatives.send", boom, raising=True
        )

        log = email_service.send_account_accepted_email(with_email)

        assert log.status == EmailStatus.FAILED

    def test_la_trace_ne_contient_que_le_type_de_l_exception(self, with_email, monkeypatch):
        """Un message d'erreur peut citer la charge utile ; son type, non."""

        def boom(self, *args, **kwargs):
            raise ConnectionRefusedError("teo@example.com refusé : mot de passe incorrect")

        monkeypatch.setattr(
            "django.core.mail.message.EmailMultiAlternatives.send", boom, raising=True
        )

        log = email_service.send_account_accepted_email(with_email)

        assert log.provider_response_summary == "ConnectionRefusedError"
        assert "mot de passe" not in log.provider_response_summary


class TestNotificationEmail:
    def test_le_relais_reprend_le_titre_et_le_message(self, with_email, mailoutbox):
        log = email_service.send_notification_email(
            with_email, title="Demande d'ami", message="alice souhaite vous ajouter."
        )

        assert log.email_type == EmailType.NOTIFICATION
        assert mailoutbox[0].subject == "Demande d'ami"
        assert "alice souhaite vous ajouter." in mailoutbox[0].body

    def test_il_n_en_dit_pas_plus_que_l_application(self, with_email, mailoutbox):
        """Un email plus bavard que l'écran deviendrait lui-même une fuite."""
        email_service.send_notification_email(with_email, title="Partage reçu", message="")

        body = mailoutbox[0].body
        assert "Partage reçu" in body
        assert with_email.username in body or with_email.first_name in body
