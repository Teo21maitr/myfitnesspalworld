"""Mot de passe oublié, réinitialisation et changement (spec 01 §1, spec 04)."""

from datetime import datetime, timedelta

import pytest
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from notifications.models import EmailLog, EmailType

pytestmark = pytest.mark.django_db

FORGOT_URL = reverse("api-v1:auth:forgot-password")
RESET_URL = reverse("api-v1:auth:reset-password")
CHANGE_URL = reverse("api-v1:account:change-password")
ME_URL = reverse("api-v1:auth:me")
LOGIN_URL = reverse("api-v1:auth:login")

PASSWORD = "un-mot-de-passe-solide-1"
NEW_PASSWORD = "un-nouveau-mot-de-passe-2"


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="teo", password=PASSWORD, status=UserStatus.ACTIVE, email="teo@example.com"
    )


def _reset_payload(user: User, token: str | None = None) -> dict:
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": token or default_token_generator.make_token(user),
        "new_password": NEW_PASSWORD,
        "new_password_confirmation": NEW_PASSWORD,
    }


# --- Mot de passe oublié -----------------------------------------------------


def test_demande_de_reinitialisation_envoie_un_email(api_client, user):
    response = api_client.post(FORGOT_URL, {"username": "TEO"})

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["teo@example.com"]
    assert EmailLog.objects.get().email_type == EmailType.PASSWORD_RESET


def test_l_email_de_reinitialisation_ne_contient_aucun_mot_de_passe(api_client, user):
    api_client.post(FORGOT_URL, {"username": "teo"})

    corps = mail.outbox[0].body
    assert PASSWORD not in corps
    assert "reinitialiser-mot-de-passe?uid=" in corps


def test_la_reponse_est_identique_pour_un_compte_inconnu(api_client, user):
    connu = api_client.post(FORGOT_URL, {"username": "teo"})
    inconnu = api_client.post(FORGOT_URL, {"username": "personne"})

    # Aucune fuite sur l'existence du compte (spec 05 §12).
    assert connu.status_code == inconnu.status_code == 200
    assert connu.json() == inconnu.json()


def test_la_reponse_est_identique_pour_un_compte_sans_email(api_client):
    User.objects.create_user(username="sansmail", password=PASSWORD, status=UserStatus.ACTIVE)

    response = api_client.post(FORGOT_URL, {"username": "sansmail"})

    assert response.status_code == 200
    assert "administrateur" in response.json()["detail"]
    assert mail.outbox == []


def test_aucun_email_pour_un_compte_suspendu(api_client, user):
    user.status = UserStatus.SUSPENDED
    user.save()

    response = api_client.post(FORGOT_URL, {"username": "teo"})

    assert response.status_code == 200
    assert mail.outbox == []


# --- Réinitialisation --------------------------------------------------------


def test_reinitialisation_change_le_mot_de_passe(api_client, user):
    response = api_client.post(RESET_URL, _reset_payload(user))

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


def test_un_token_deja_utilise_est_refuse(api_client, user):
    payload = _reset_payload(user)

    assert api_client.post(RESET_URL, payload).status_code == 200

    # Le token dérive du hash du mot de passe : il est mort après usage.
    second = api_client.post(RESET_URL, payload)
    assert second.status_code == 400
    assert second.json()["code"] == "invalid_reset_token"


def test_un_token_expire_est_refuse(api_client, user, monkeypatch):
    passe = datetime.now() - timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 60)
    monkeypatch.setattr(PasswordResetTokenGenerator, "_now", lambda self: passe)
    token_expire = default_token_generator.make_token(user)
    monkeypatch.undo()

    response = api_client.post(RESET_URL, _reset_payload(user, token=token_expire))

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_reset_token"


def test_un_token_falsifie_est_refuse(api_client, user):
    response = api_client.post(RESET_URL, _reset_payload(user, token="bidon-123"))

    assert response.status_code == 400


def test_un_uid_inconnu_est_refuse(api_client, user):
    payload = _reset_payload(user)
    payload["uid"] = urlsafe_base64_encode(force_bytes(999999))

    assert api_client.post(RESET_URL, payload).status_code == 400


def test_reinitialisation_refuse_un_mot_de_passe_faible(api_client, user):
    payload = _reset_payload(user)
    payload["new_password"] = payload["new_password_confirmation"] = "1234"

    response = api_client.post(RESET_URL, payload)

    assert response.status_code == 400
    assert "new_password" in response.json()["errors"]


def test_reinitialisation_revoque_les_sessions(api_client, user):
    refresh = build_refresh_token(user)
    api_client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    assert api_client.get(ME_URL).status_code == 200

    api_client.post(RESET_URL, _reset_payload(user))

    assert api_client.get(ME_URL).status_code == 401


# --- Changement de mot de passe ----------------------------------------------


def test_changement_de_mot_de_passe(auth_client, active_user):
    response = auth_client.post(
        CHANGE_URL,
        {
            "current_password": "motdepasse-de-test-123",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200
    active_user.refresh_from_db()
    assert active_user.check_password(NEW_PASSWORD)


def test_changement_refuse_si_le_mot_de_passe_actuel_est_faux(auth_client):
    response = auth_client.post(
        CHANGE_URL,
        {
            "current_password": "mauvais-mdp-1",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
    )

    assert response.status_code == 400
    assert "current_password" in response.json()["errors"]


def test_changement_refuse_si_la_confirmation_differe(auth_client):
    response = auth_client.post(
        CHANGE_URL,
        {
            "current_password": "motdepasse-de-test-123",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": "autre-mot-de-passe-9",
        },
    )

    assert response.status_code == 400
    assert "new_password_confirmation" in response.json()["errors"]


def test_changement_exige_une_authentification(api_client):
    assert api_client.post(CHANGE_URL, {}).status_code == 401


def test_changement_garde_l_appareil_courant_et_deconnecte_les_autres(
    api_client, auth_client, active_user
):
    """Stratégie retenue : sémantique de `update_session_auth_hash`."""
    autre_appareil = build_refresh_token(active_user)
    api_client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(autre_appareil.access_token)
    assert api_client.get(ME_URL).status_code == 200

    response = auth_client.post(
        CHANGE_URL,
        {
            "current_password": "motdepasse-de-test-123",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
    )

    # L'appareil courant reçoit des cookies neufs et reste connecté.
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    auth_client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = response.cookies[
        settings.AUTH_COOKIE_ACCESS_NAME
    ].value
    assert auth_client.get(ME_URL).status_code == 200

    # Les autres appareils sont déconnectés.
    assert api_client.get(ME_URL).status_code == 401


def test_le_nouveau_mot_de_passe_permet_de_se_reconnecter(api_client, auth_client, active_user):
    auth_client.post(
        CHANGE_URL,
        {
            "current_password": "motdepasse-de-test-123",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
    )

    response = api_client.post(
        LOGIN_URL, {"username": active_user.username, "password": NEW_PASSWORD}
    )

    assert response.status_code == 200
