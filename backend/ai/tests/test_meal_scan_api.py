"""API Meal Scan (spec 04 §10, spec 05 §12).

Le test qui compte est le dernier de `TestNothingIsInvented` : de l'appel HTTP
jusqu'à la réponse, aucune valeur nutritionnelle inventée par le fournisseur ne
doit apparaître, et aucune entrée de journal ne doit être créée.
"""

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from ai.services import images as image_store
from common.models import AppSetting, AsyncTask, TaskStatus
from diary.models import DiaryEntry

from .conftest import JPEG_BYTES

pytestmark = pytest.mark.django_db

SCAN_URL = reverse("api-v1:ai:meal-scan")


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[django_settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[django_settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


def photo(name: str = "repas.jpg"):
    return SimpleUploadedFile(name, JPEG_BYTES, content_type="image/jpeg")


@pytest.fixture
def stashed_keys(monkeypatch) -> list[str]:
    """Espionne le dépôt des images pour vérifier qu'elles disparaissent."""
    recorded: list[str] = []
    original = image_store.stash

    def spy(images):
        keys = original(images)
        recorded.extend(keys)
        return keys

    monkeypatch.setattr(image_store, "stash", spy)
    return recorded


def scan(client, files=None):
    return client.post(
        SCAN_URL, {"images": files if files is not None else [photo()]}, format="multipart"
    )


class TestNothingIsInvented:
    def test_le_scan_ne_cree_aucune_entree_de_journal(self, ai_enabled, active_user, chicken):
        """L'IA suggère, l'utilisateur confirme (CLAUDE.md §2)."""
        response = scan(client_for(active_user))

        assert response.status_code == 202
        assert DiaryEntry.objects.count() == 0

    def test_les_calories_du_fournisseur_n_apparaissent_jamais(
        self, ai_enabled, active_user, chicken, apricot
    ):
        """Le fournisseur simulé renvoie volontairement un `energy_kcal` faux.

        Il ne doit se retrouver ni dans la réponse, ni dans la tâche.
        """
        response = scan(client_for(active_user))

        assert "9999" not in str(response.json())

        suggestion = response.json()["result"]["suggestions"][0]
        assert suggestion["label"] == "poulet"
        # La valeur affichée est celle de la fiche, pas celle de la photo.
        assert suggestion["candidates"][0]["nutrition"]["energy_kcal"] == "120.000"

    def test_les_suggestions_portent_les_aliments_de_la_base(
        self, ai_enabled, active_user, chicken, apricot
    ):
        response = scan(client_for(active_user))

        suggestions = response.json()["result"]["suggestions"]
        assert [item["label"] for item in suggestions] == ["poulet", "abricot"]
        assert suggestions[0]["candidates"][0]["id"] == chicken.pk
        assert suggestions[1]["candidates"][0]["id"] == apricot.pk


class TestResponse:
    def test_la_tache_est_creee_au_nom_de_l_appelant(self, ai_enabled, active_user, chicken):
        response = scan(client_for(active_user))

        task = AsyncTask.objects.get()
        assert task.user == active_user
        assert str(task.pk) == response.json()["id"]
        assert response.json()["status"] == TaskStatus.SUCCESS
        assert task.expires_at is not None

    def test_les_images_ne_survivent_pas_a_l_appel(
        self, ai_enabled, active_user, chicken, stashed_keys
    ):
        scan(client_for(active_user))

        assert stashed_keys, "aucune image n'a été déposée : le test ne prouve rien"
        assert all(cache.get(key) is None for key in stashed_keys)

    def test_plusieurs_photos_sont_acceptees(self, ai_enabled, active_user, chicken):
        response = scan(client_for(active_user), [photo("face.jpg"), photo("profil.jpg")])

        assert response.status_code == 202


class TestKillSwitch:
    def test_l_ia_coupee_par_l_administrateur_repond_503(self, ai_enabled, active_user):
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=False)

        response = scan(client_for(active_user))

        assert response.status_code == 503
        assert response.json()["code"] == "ai_disabled"

    def test_l_ia_reactivee_repond_de_nouveau(self, ai_enabled, active_user, chicken):
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=True)

        assert scan(client_for(active_user)).status_code == 202

    def test_un_reglage_incoherent_ne_coupe_pas_l_ia(self, ai_enabled, active_user, chicken):
        """Une valeur saisie à la main peut être n'importe quoi."""
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value="peut-être")

        assert scan(client_for(active_user)).status_code == 202

    def test_l_ia_non_deployee_repond_503(self, ai_enabled, active_user):
        ai_enabled.AI_ENABLED = False

        response = scan(client_for(active_user))

        assert response.status_code == 503
        assert response.json()["code"] == "ai_disabled"

    def test_sans_cle_d_api_l_ia_repond_503(self, ai_enabled, active_user):
        ai_enabled.AI_PROVIDER = "anthropic"
        ai_enabled.ANTHROPIC_API_KEY = ""

        response = scan(client_for(active_user))

        assert response.status_code == 503
        assert response.json()["code"] == "ai_disabled"

    def test_l_ia_coupee_ne_gene_pas_le_reste(self, ai_enabled, active_user, chicken):
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=False)
        client = client_for(active_user)

        assert scan(client).status_code == 503
        assert client.get(reverse("api-v1:foods:search"), {"q": "poulet"}).status_code == 200

    def test_aucune_tache_n_est_creee_quand_l_ia_est_coupee(self, ai_enabled, active_user):
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=False)

        scan(client_for(active_user))

        assert AsyncTask.objects.count() == 0


class TestValidation:
    def test_sans_photo_la_requete_est_refusee(self, ai_enabled, active_user):
        response = scan(client_for(active_user), [])

        assert response.status_code == 400

    def test_trop_de_photos(self, ai_enabled, active_user):
        response = scan(client_for(active_user), [photo(f"{index}.jpg") for index in range(4)])

        assert response.status_code == 400

    def test_un_fichier_qui_n_est_pas_une_image(self, ai_enabled, active_user):
        upload = SimpleUploadedFile("doc.pdf", b"%PDF-1.4", content_type="application/pdf")

        response = scan(client_for(active_user), [upload])

        assert response.status_code == 400

    def test_aucune_tache_n_est_creee_sur_un_envoi_invalide(self, ai_enabled, active_user):
        scan(client_for(active_user), [])

        assert AsyncTask.objects.count() == 0


class TestPermissions:
    def test_un_appel_anonyme_est_refuse(self, ai_enabled, db):
        assert scan(APIClient()).status_code == 401

    def test_un_compte_suspendu_est_refuse(self, ai_enabled, db):
        suspended = User.objects.create_user(
            username="suspendu", password="un-mot-de-passe-solide-1", status=UserStatus.SUSPENDED
        )

        assert scan(client_for(suspended)).status_code == 401

    def test_le_quota_ia_s_applique(self, ai_enabled, active_user, chicken):
        client = client_for(active_user)

        statuts = [scan(client).status_code for _ in range(31)]

        assert 429 in statuts
