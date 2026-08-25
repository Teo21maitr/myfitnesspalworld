"""Demandes d'inscription : API, service et cycle de vie (spec 01 §1)."""

import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import RegistrationRequest, User, UserStatus
from accounts.services.registration import (
    UsernameUnavailableError,
    accept_registration_request,
    reject_registration_request,
    username_is_available,
)
from notifications.models import EmailLog, EmailStatus, EmailType

pytestmark = pytest.mark.django_db

URL = reverse("api-v1:auth:register-request")

VALID_PAYLOAD = {
    "first_name": "Téo",
    "last_name": "Maitrot",
    "username": "teo",
    "email": "teo@example.com",
    "password": "un-mot-de-passe-solide-1",
    "password_confirmation": "un-mot-de-passe-solide-1",
}


def test_une_demande_valide_est_enregistree(api_client):
    response = api_client.post(URL, VALID_PAYLOAD)

    assert response.status_code == 201
    assert "administrateur" in response.json()["detail"]

    demande = RegistrationRequest.objects.get(username="teo")
    assert demande.normalized_username == "teo"
    assert demande.email == "teo@example.com"


def test_le_mot_de_passe_est_hache_et_jamais_renvoye(api_client):
    response = api_client.post(URL, VALID_PAYLOAD)

    assert "password" not in response.json()

    demande = RegistrationRequest.objects.get(username="teo")
    assert demande.password != VALID_PAYLOAD["password"]
    assert demande.password.startswith(("pbkdf2_", "argon2", "md5$"))


def test_l_email_est_facultatif(api_client):
    payload = {**VALID_PAYLOAD}
    payload.pop("email")

    response = api_client.post(URL, payload)

    assert response.status_code == 201
    assert RegistrationRequest.objects.get(username="teo").email is None


def test_username_deja_pris_par_un_compte_est_refuse(api_client, active_user):
    response = api_client.post(URL, {**VALID_PAYLOAD, "username": active_user.username.upper()})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert "username" in body["errors"]


def test_username_deja_pris_par_une_demande_est_refuse(api_client):
    api_client.post(URL, VALID_PAYLOAD)

    response = api_client.post(URL, {**VALID_PAYLOAD, "username": "TEO"})

    assert response.status_code == 400
    assert "username" in response.json()["errors"]


def test_confirmation_differente_est_refusee(api_client):
    response = api_client.post(
        URL, {**VALID_PAYLOAD, "password_confirmation": "autre-mot-de-passe-9"}
    )

    assert response.status_code == 400
    assert "password_confirmation" in response.json()["errors"]


def test_mot_de_passe_trop_faible_est_refuse(api_client):
    response = api_client.post(
        URL, {**VALID_PAYLOAD, "password": "1234", "password_confirmation": "1234"}
    )

    assert response.status_code == 400
    assert "password" in response.json()["errors"]


def test_champs_obligatoires(api_client):
    response = api_client.post(URL, {})

    errors = response.json()["errors"]
    assert response.status_code == 400
    for field in ("first_name", "last_name", "username", "password", "password_confirmation"):
        assert field in errors


# --- Service d'acceptation / refus ------------------------------------------


def _create_request(**overrides) -> RegistrationRequest:
    payload = {
        "first_name": "Téo",
        "last_name": "Maitrot",
        "username": "teo",
        "email": "teo@example.com",
        **overrides,
    }
    raw_password = payload.pop("password", "un-mot-de-passe-solide-1")
    demande = RegistrationRequest(**payload)
    demande.set_password(raw_password)
    demande.save()
    return demande


def test_acceptation_cree_un_compte_actif_et_supprime_la_demande():
    demande = _create_request()
    password_hash = demande.password

    user = accept_registration_request(demande)

    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True
    assert user.first_name == "Téo"
    assert user.email == "teo@example.com"
    # Le hash est transféré tel quel : le mot de passe choisi reste valable.
    assert user.password == password_hash
    assert user.check_password("un-mot-de-passe-solide-1")
    assert RegistrationRequest.objects.count() == 0


def test_acceptation_cree_le_profil_et_les_parametres():
    user = accept_registration_request(_create_request())

    assert user.profile.onboarding_completed is False
    assert user.settings.theme_mode == "system"


def test_acceptation_envoie_un_email_et_le_journalise(django_capture_on_commit_callbacks):
    # L'email n'est déclenché qu'après commit : aucune notification ne part
    # si la création du compte échoue.
    with django_capture_on_commit_callbacks(execute=True):
        accept_registration_request(_create_request())

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["teo@example.com"]

    log = EmailLog.objects.get()
    assert log.email_type == EmailType.ACCOUNT_ACCEPTED
    assert log.status == EmailStatus.SENT


def test_acceptation_sans_email_n_envoie_rien(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        accept_registration_request(_create_request(email=None))

    assert mail.outbox == []
    assert EmailLog.objects.count() == 0


def test_acceptation_refusee_si_le_username_a_ete_pris_entretemps(
    active_user, django_capture_on_commit_callbacks
):
    demande = _create_request(username=active_user.username.upper())

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(UsernameUnavailableError),
    ):
        accept_registration_request(demande)

    # Rien n'a été créé ni supprimé.
    assert RegistrationRequest.objects.filter(pk=demande.pk).exists()
    assert mail.outbox == []


def test_refus_supprime_la_demande_et_previent_le_demandeur(
    django_capture_on_commit_callbacks,
):
    demande = _create_request()

    with django_capture_on_commit_callbacks(execute=True):
        reject_registration_request(demande)

    assert RegistrationRequest.objects.count() == 0
    assert User.objects.filter(normalized_username="teo").exists() is False
    assert len(mail.outbox) == 1

    log = EmailLog.objects.get()
    assert log.email_type == EmailType.ACCOUNT_REJECTED
    assert log.user is None


def test_une_nouvelle_demande_est_possible_apres_un_refus(api_client):
    demande = _create_request()
    reject_registration_request(demande)

    response = api_client.post(URL, VALID_PAYLOAD)

    assert response.status_code == 201


def test_une_demande_en_attente_ne_permet_pas_de_se_connecter(api_client):
    """Aucun `User` n'existe avant l'acceptation.

    La connexion renvoie donc le message générique, ce qui évite de révéler
    qu'une demande est en cours pour ce nom d'utilisateur (spec 05 §12).
    """
    from django.urls import reverse

    api_client.post(URL, VALID_PAYLOAD)

    response = api_client.post(
        reverse("api-v1:auth:login"),
        {"username": "teo", "password": VALID_PAYLOAD["password"]},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert User.objects.filter(normalized_username="teo").exists() is False


def test_username_is_available_ignore_la_casse(active_user):
    assert username_is_available(active_user.username.upper()) is False
    assert username_is_available("libre") is True
    assert username_is_available("   ") is False


# --- Commandes de gestion ---------------------------------------------------


def test_commande_accept_registration_request():
    from django.core.management import call_command

    _create_request()
    call_command("accept_registration_request", "TEO")

    assert User.objects.get(normalized_username="teo").status == UserStatus.ACTIVE


def test_commande_reject_registration_request():
    from django.core.management import call_command

    _create_request()
    call_command("reject_registration_request", "teo")

    assert RegistrationRequest.objects.count() == 0


def test_commande_sur_une_demande_inexistante():
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="Aucune demande"):
        call_command("accept_registration_request", "inconnu")
