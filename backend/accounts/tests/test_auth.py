"""Authentification : connexion, session, CSRF et révocation (spec 05)."""

import pytest
from django.conf import settings
from django.urls import reverse

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token

pytestmark = pytest.mark.django_db

LOGIN_URL = reverse("api-v1:auth:login")
ME_URL = reverse("api-v1:auth:me")
LOGOUT_URL = reverse("api-v1:auth:logout")
LOGOUT_ALL_URL = reverse("api-v1:auth:logout-all")
REFRESH_URL = reverse("api-v1:auth:refresh")
CSRF_URL = reverse("api-v1:auth:csrf")

PASSWORD = "un-mot-de-passe-solide-1"


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="Teo", password=PASSWORD, status=UserStatus.ACTIVE, email="teo@example.com"
    )


# --- Connexion ---------------------------------------------------------------


def test_connexion_pose_les_cookies_httponly(api_client, user):
    response = api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    assert response.status_code == 200
    access = response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]
    refresh = response.cookies[settings.AUTH_COOKIE_REFRESH_NAME]

    assert access["httponly"] is True
    assert refresh["httponly"] is True
    # Le cookie de refresh ne circule que sur les routes d'authentification.
    assert refresh["path"] == settings.AUTH_COOKIE_REFRESH_PATH
    assert access["path"] == "/"


def test_connexion_insensible_a_la_casse(api_client, user):
    response = api_client.post(LOGIN_URL, {"username": "tEo", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["username"] == "Teo"


def test_connexion_ne_renvoie_aucun_champ_sensible(api_client, user):
    body = api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD}).json()

    assert set(body) == {
        "id",
        "username",
        "first_name",
        "last_name",
        "email",
        "status",
        "is_staff",
        "onboarding_completed",
    }
    assert "password" not in body
    assert "token_version" not in body
    assert "normalized_username" not in body


def test_mauvais_mot_de_passe_est_refuse(api_client, user):
    response = api_client.post(LOGIN_URL, {"username": "Teo", "password": "mauvais-mdp-1"})

    assert response.status_code == 401
    assert response.json()["message"] == "Nom d’utilisateur ou mot de passe incorrect."


def test_compte_inexistant_renvoie_le_meme_message(api_client, user):
    """Aucune énumération de comptes possible (spec 05 §12)."""
    inconnu = api_client.post(LOGIN_URL, {"username": "inconnu", "password": PASSWORD})
    mauvais = api_client.post(LOGIN_URL, {"username": "Teo", "password": "mauvais-mdp-1"})

    assert inconnu.status_code == mauvais.status_code == 401
    assert inconnu.json()["message"] == mauvais.json()["message"]


def test_compte_en_attente_ne_peut_pas_se_connecter(api_client):
    User.objects.create_user(username="attente", password=PASSWORD, status=UserStatus.PENDING)

    response = api_client.post(LOGIN_URL, {"username": "attente", "password": PASSWORD})

    assert response.status_code == 401
    assert response.json()["code"] == "account_pending"


def test_compte_suspendu_ne_peut_pas_se_connecter(api_client, user):
    user.status = UserStatus.SUSPENDED
    user.save()

    response = api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    assert response.status_code == 401
    assert response.json()["code"] == "account_suspended"


def test_suspension_invalide_une_session_existante(api_client, user):
    api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})
    assert api_client.get(ME_URL).status_code == 200

    user.status = UserStatus.SUSPENDED
    user.save()

    assert api_client.get(ME_URL).status_code == 401


# --- Endpoint /me/ -----------------------------------------------------------


def test_me_exige_une_authentification(api_client):
    response = api_client.get(ME_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_me_renvoie_le_compte_courant(auth_client, active_user):
    response = auth_client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["username"] == active_user.username
    assert response.json()["onboarding_completed"] is False


def test_me_seme_le_cookie_csrf(api_client, user):
    api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    response = api_client.get(ME_URL)

    assert settings.CSRF_COOKIE_NAME in response.cookies


def test_csrf_endpoint_seme_le_cookie(api_client):
    response = api_client.get(CSRF_URL)

    assert response.status_code == 200
    assert settings.CSRF_COOKIE_NAME in response.cookies


# --- CSRF --------------------------------------------------------------------


def test_ecriture_par_cookie_sans_entete_csrf_est_refusee(user):
    """Le cookie d'authentification seul ne suffit pas à écrire."""
    from rest_framework.test import APIClient

    client = APIClient(enforce_csrf_checks=True)
    client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    response = client.post(LOGOUT_URL)

    assert response.status_code == 403
    assert "CSRF" in response.json()["message"]


def test_ecriture_par_cookie_avec_entete_csrf_est_acceptee(user):
    from rest_framework.test import APIClient

    client = APIClient(enforce_csrf_checks=True)
    client.get(CSRF_URL)
    client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    csrf_token = client.cookies[settings.CSRF_COOKIE_NAME].value
    response = client.post(LOGOUT_URL, HTTP_X_CSRFTOKEN=csrf_token)

    assert response.status_code == 204


def test_lecture_par_cookie_ne_demande_pas_de_csrf(user):
    from rest_framework.test import APIClient

    client = APIClient(enforce_csrf_checks=True)
    client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    assert client.get(ME_URL).status_code == 200


# --- Refresh -----------------------------------------------------------------


def test_refresh_renouvelle_les_cookies(api_client, user):
    api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})
    ancien_refresh = api_client.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    response = api_client.post(REFRESH_URL)

    assert response.status_code == 200
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value != ancien_refresh


def test_refresh_sans_cookie_est_refuse(api_client):
    response = api_client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "no_refresh_cookie"


def test_un_refresh_deja_utilise_est_refuse(api_client, user):
    api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})
    ancien_refresh = api_client.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    api_client.post(REFRESH_URL)

    # Rejeu de l'ancien refresh : il a été mis en liste noire par la rotation.
    api_client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = ancien_refresh
    assert api_client.post(REFRESH_URL).status_code == 401


# --- Déconnexion -------------------------------------------------------------


def test_logout_efface_les_cookies(auth_client):
    response = auth_client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value == ""
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value == ""


def test_logout_exige_une_authentification(api_client):
    assert api_client.post(LOGOUT_URL).status_code == 401


def test_logout_all_invalide_un_access_token_deja_emis(api_client, active_user):
    """Un access token est sans état : seule la version de session le révoque."""
    autre_appareil = build_refresh_token(active_user)
    api_client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(autre_appareil.access_token)
    assert api_client.get(ME_URL).status_code == 200

    session_courante = build_refresh_token(active_user)
    from rest_framework.test import APIClient

    client = APIClient()
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(session_courante.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(session_courante)
    assert client.post(LOGOUT_ALL_URL).status_code == 204

    response = api_client.get(ME_URL)
    assert response.status_code == 401
    assert response.json()["code"] == "session_revoked"


def test_logout_all_invalide_les_refresh_tokens(api_client, user):
    api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})
    refresh_avant = api_client.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    api_client.post(LOGOUT_ALL_URL)

    api_client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = refresh_avant
    assert api_client.post(REFRESH_URL).status_code == 401


def test_logout_all_incremente_la_version_de_session(auth_client, active_user):
    version_avant = active_user.token_version

    auth_client.post(LOGOUT_ALL_URL)

    active_user.refresh_from_db()
    assert active_user.token_version == version_avant + 1


# --- Limitation de débit -----------------------------------------------------


def test_le_renouvellement_ne_consomme_pas_le_quota_de_connexion(api_client, user):
    """Quotas distincts.

    L'application déclenche un renouvellement à chaque chargement de page :
    s'il partageait le quota de la connexion, un visiteur déconnecté finirait
    par ne plus pouvoir se connecter.
    """
    for _ in range(15):
        api_client.post(REFRESH_URL)

    response = api_client.post(LOGIN_URL, {"username": "Teo", "password": PASSWORD})

    assert response.status_code == 200


def test_les_tentatives_de_connexion_sont_limitees(api_client, user):
    """Les endpoints sensibles sont throttlés (spec 05 §12)."""
    statuts = [
        api_client.post(LOGIN_URL, {"username": "Teo", "password": "mauvais-mdp-1"}).status_code
        for _ in range(12)
    ]

    assert 429 in statuts
