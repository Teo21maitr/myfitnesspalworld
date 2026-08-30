"""Profil, paramètres et suppression de compte (spec 04 §2, §20, spec 05)."""

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ThemeMode, User, UserProfile, UserSettings, UserStatus
from accounts.services.sessions import build_refresh_token
from notifications.models import EmailLog, EmailStatus, EmailType

pytestmark = pytest.mark.django_db

PROFILE_URL = reverse("api-v1:profile:profile")
SETTINGS_URL = reverse("api-v1:profile:settings")
ACCOUNT_URL = reverse("api-v1:account:account")
ME_URL = reverse("api-v1:auth:me")


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


# --- Création automatique ----------------------------------------------------


def test_le_profil_et_les_parametres_sont_crees_avec_le_compte(active_user):
    assert UserProfile.objects.filter(user=active_user).exists()
    assert UserSettings.objects.filter(user=active_user).exists()
    assert active_user.settings.theme_mode == ThemeMode.SYSTEM
    assert active_user.settings.language == "fr"


# --- Profil ------------------------------------------------------------------


def test_profil_exige_une_authentification(api_client):
    assert api_client.get(PROFILE_URL).status_code == 401


def test_lecture_du_profil(auth_client, active_user):
    body = auth_client.get(PROFILE_URL).json()

    assert body["username"] == active_user.username
    assert body["onboarding_completed"] is False
    assert "password" not in body
    assert "token_version" not in body
    assert "normalized_username" not in body


def test_modification_de_l_identite(auth_client, active_user):
    response = auth_client.patch(
        PROFILE_URL, {"first_name": "Téo", "last_name": "Maitrot", "email": "teo@example.com"}
    )

    assert response.status_code == 200
    active_user.refresh_from_db()
    assert active_user.first_name == "Téo"
    assert active_user.email == "teo@example.com"


def test_le_username_reste_modifiable(auth_client, active_user):
    response = auth_client.patch(PROFILE_URL, {"username": "Teo.Maitrot"})

    assert response.status_code == 200
    active_user.refresh_from_db()
    assert active_user.username == "Teo.Maitrot"
    assert active_user.normalized_username == "teo.maitrot"


def test_changer_seulement_la_casse_de_son_username_est_permis(auth_client, active_user):
    response = auth_client.patch(PROFILE_URL, {"username": active_user.username.upper()})

    assert response.status_code == 200


def test_un_username_deja_pris_est_refuse(auth_client, other_user):
    response = auth_client.patch(PROFILE_URL, {"username": other_user.username.upper()})

    assert response.status_code == 400
    assert "username" in response.json()["errors"]


def test_l_email_peut_etre_vide(auth_client, active_user):
    auth_client.patch(PROFILE_URL, {"email": "teo@example.com"})

    response = auth_client.patch(PROFILE_URL, {"email": ""})

    assert response.status_code == 200
    active_user.refresh_from_db()
    assert active_user.email is None


def test_le_statut_n_est_pas_modifiable_par_l_utilisateur(auth_client, active_user):
    auth_client.patch(PROFILE_URL, {"status": UserStatus.SUSPENDED})

    active_user.refresh_from_db()
    assert active_user.status == UserStatus.ACTIVE


def test_is_staff_n_est_pas_modifiable_par_l_utilisateur(auth_client, active_user):
    auth_client.patch(PROFILE_URL, {"is_staff": True})

    active_user.refresh_from_db()
    assert active_user.is_staff is False


def test_un_utilisateur_ne_voit_que_son_propre_profil(active_user, other_user):
    """Aucun accès horizontal : l'API ne cible que l'utilisateur courant."""
    body = client_for(other_user).get(PROFILE_URL).json()

    assert body["username"] == other_user.username
    assert body["username"] != active_user.username


def test_un_utilisateur_ne_peut_pas_modifier_le_profil_d_un_autre(active_user, other_user):
    client_for(other_user).patch(PROFILE_URL, {"first_name": "Intrus"})

    active_user.refresh_from_db()
    assert active_user.first_name != "Intrus"


def test_un_compte_suspendu_n_accede_pas_au_profil(active_user):
    client = client_for(active_user)
    active_user.status = UserStatus.SUSPENDED
    active_user.save()

    assert client.get(PROFILE_URL).status_code == 401


# --- Paramètres --------------------------------------------------------------


def test_lecture_des_parametres(auth_client):
    body = auth_client.get(SETTINGS_URL).json()

    # Le catalogue des langues varie ; le reste du contrat est figé.
    catalogue = body.pop("available_food_search_languages")
    assert body == {
        "language": "fr",
        "theme_mode": "system",
        "date_format": "DD/MM/YYYY",
        "food_search_languages": ["fr", "en"],
    }
    assert {"code": "sv", "label": "Suédois"} in catalogue


@pytest.mark.parametrize("theme", ["light", "dark", "system"])
def test_le_theme_est_modifiable(auth_client, active_user, theme):
    response = auth_client.patch(SETTINGS_URL, {"theme_mode": theme})

    assert response.status_code == 200
    active_user.settings.refresh_from_db()
    assert active_user.settings.theme_mode == theme


def test_un_theme_inconnu_est_refuse(auth_client):
    response = auth_client.patch(SETTINGS_URL, {"theme_mode": "neon"})

    assert response.status_code == 400
    assert "theme_mode" in response.json()["errors"]


def test_la_langue_n_est_pas_modifiable(auth_client, active_user):
    auth_client.patch(SETTINGS_URL, {"language": "en"})

    active_user.settings.refresh_from_db()
    assert active_user.settings.language == "fr"


def test_les_parametres_exigent_une_authentification(api_client):
    assert api_client.get(SETTINGS_URL).status_code == 401


# --- Suppression de compte ---------------------------------------------------


def test_suppression_avec_mauvaise_confirmation(auth_client, active_user):
    response = auth_client.delete(ACCOUNT_URL, {"username_confirmation": "pas-le-bon"})

    assert response.status_code == 400
    assert "username_confirmation" in response.json()["errors"]
    assert User.objects.filter(pk=active_user.pk).exists()


def test_la_confirmation_est_sensible_a_la_casse(auth_client, active_user):
    response = auth_client.delete(
        ACCOUNT_URL, {"username_confirmation": active_user.username.upper()}
    )

    assert response.status_code == 400
    assert User.objects.filter(pk=active_user.pk).exists()


def test_suppression_avec_la_bonne_confirmation(auth_client, active_user):
    pk = active_user.pk

    response = auth_client.delete(ACCOUNT_URL, {"username_confirmation": active_user.username})

    assert response.status_code == 204
    assert User.objects.filter(pk=pk).exists() is False
    # Les données liées disparaissent avec le compte.
    assert UserProfile.objects.filter(user_id=pk).exists() is False
    assert UserSettings.objects.filter(user_id=pk).exists() is False


def test_suppression_efface_les_cookies_et_revoque_la_session(auth_client, active_user):
    response = auth_client.delete(ACCOUNT_URL, {"username_confirmation": active_user.username})

    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value == ""
    assert auth_client.get(ME_URL).status_code == 401


def test_suppression_efface_les_traces_d_email(auth_client, active_user):
    EmailLog.objects.create(
        user=active_user,
        email_type=EmailType.PASSWORD_RESET,
        recipient="teo@example.com",
        status=EmailStatus.SENT,
    )

    auth_client.delete(ACCOUNT_URL, {"username_confirmation": active_user.username})

    assert EmailLog.objects.count() == 0


def test_suppression_exige_une_authentification(api_client):
    assert api_client.delete(ACCOUNT_URL, {"username_confirmation": "teo"}).status_code == 401


def test_supprimer_son_compte_n_affecte_pas_les_autres(auth_client, active_user, other_user):
    auth_client.delete(ACCOUNT_URL, {"username_confirmation": active_user.username})

    assert User.objects.filter(pk=other_user.pk).exists()


class TestFoodSearchLanguages:
    """Langues de recherche de produits (spec 11 §3).

    Réglage par compte : on ne cherche pas les mêmes produits selon le pays où
    l'on fait ses courses.
    """

    def test_un_nouveau_compte_cherche_en_francais_et_en_anglais(self, active_user):
        assert active_user.settings.food_search_languages == ["fr", "en"]

    def test_le_defaut_du_modele_suit_le_catalogue(self):
        """Le défaut est écrit dans `accounts` pour ne pas faire dépendre une
        migration d'une autre application. Ce test empêche les deux de
        diverger."""
        from accounts.models import default_food_search_languages
        from nutrition.services.off_client import (
            DEFAULT_SEARCH_LANGUAGES,
            SUPPORTED_SEARCH_LANGUAGES,
        )

        assert default_food_search_languages() == list(DEFAULT_SEARCH_LANGUAGES)
        assert all(code in SUPPORTED_SEARCH_LANGUAGES for code in DEFAULT_SEARCH_LANGUAGES)

    def test_le_reglage_se_modifie(self, active_user):
        response = client_for(active_user).patch(
            SETTINGS_URL, {"food_search_languages": ["fr", "sv"]}, format="json"
        )

        assert response.status_code == 200
        active_user.settings.refresh_from_db()
        assert active_user.settings.food_search_languages == ["fr", "sv"]

    def test_le_catalogue_accompagne_les_reglages(self, active_user):
        """Renvoyé par le serveur plutôt que recopié dans le frontend."""
        payload = client_for(active_user).get(SETTINGS_URL).json()

        codes = [entry["code"] for entry in payload["available_food_search_languages"]]
        assert "sv" in codes
        assert all("label" in entry for entry in payload["available_food_search_languages"])

    def test_une_langue_inconnue_est_refusee(self, active_user):
        response = client_for(active_user).patch(
            SETTINGS_URL, {"food_search_languages": ["fr", "klingon"]}, format="json"
        )

        assert response.status_code == 400

    def test_une_liste_vide_est_refusee(self, active_user):
        """Chercher dans aucune langue ne renverrait rien."""
        response = client_for(active_user).patch(
            SETTINGS_URL, {"food_search_languages": []}, format="json"
        )

        assert response.status_code == 400

    def test_trop_de_langues_est_refuse(self, active_user):
        response = client_for(active_user).patch(
            SETTINGS_URL,
            {"food_search_languages": ["fr", "en", "sv", "de", "es", "it"]},
            format="json",
        )

        assert response.status_code == 400

    def test_les_doublons_sont_retires_sans_changer_l_ordre(self, active_user):
        response = client_for(active_user).patch(
            SETTINGS_URL, {"food_search_languages": ["sv", "fr", "sv"]}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["food_search_languages"] == ["sv", "fr"]


def test_la_suppression_du_compte_emporte_les_photos(
    auth_client, active_user, fake_storage, jpeg_bytes
):
    """La cascade emporte les lignes ; les fichiers, il faut aller les chercher.

    C'est le chemin le plus facile à oublier : `user.delete()` a l'air de tout
    emporter, et rien ne signale les objets restés dans le seau (spec 05 §11).
    """
    from datetime import date

    from progress.models import ProgressPhotoGroup
    from progress.services import photos as photos_service

    group = ProgressPhotoGroup.objects.create(user=active_user, date=date(2026, 8, 26))
    photos_service.store_photo(group, data=jpeg_bytes, photo_type="front")
    photos_service.store_photo(group, data=jpeg_bytes, photo_type="side")
    assert fake_storage.count() == 2

    response = auth_client.delete(
        ACCOUNT_URL, {"username_confirmation": active_user.username}, format="json"
    )

    assert response.status_code == 204
    assert fake_storage.count() == 0
