"""API de lecture d'étiquette (spec 04 §10).

Le test qui compte est le premier : de l'appel HTTP jusqu'à la réponse, une
valeur que la photo n'a pas donnée doit rester nulle — et aucun aliment ne doit
être créé sans que l'utilisateur l'ait voulu.
"""

import pytest
from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from common.models import AppSetting, AsyncTask, TaskType
from nutrition.models import Food

from .conftest import JPEG_BYTES

pytestmark = pytest.mark.django_db

LABEL_URL = reverse("api-v1:ai:label-scan")


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[django_settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[django_settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


def scan(client, files=None):
    photo = SimpleUploadedFile("etiquette.jpg", JPEG_BYTES, content_type="image/jpeg")
    return client.post(
        LABEL_URL, {"images": files if files is not None else [photo]}, format="multipart"
    )


class TestNothingIsInvented:
    def test_une_valeur_non_lue_traverse_nulle(self, ai_enabled, active_user):
        """Le fournisseur simulé laisse `fiber_g` nul : il doit le rester."""
        response = scan(client_for(active_user))

        assert response.status_code == 202
        brouillon = response.json()["result"]
        assert brouillon["draft"]["nutrition"]["fiber_g"] is None
        assert "fiber_g" in brouillon["unreadable"]

    def test_aucun_aliment_n_est_cree(self, ai_enabled, active_user):
        """C'est l'utilisateur qui crée la fiche, après vérification."""
        avant = Food.objects.count()

        scan(client_for(active_user))

        assert Food.objects.count() == avant

    def test_les_valeurs_lues_sont_rendues(self, ai_enabled, active_user):
        brouillon = scan(client_for(active_user)).json()["result"]["draft"]

        assert brouillon["name"] == "Produit de démonstration"
        assert brouillon["reference_unit"] == "g"
        assert brouillon["nutrition"]["energy_kcal"] == "250.000"


class TestTask:
    def test_la_tache_porte_son_type(self, ai_enabled, active_user):
        scan(client_for(active_user))

        assert AsyncTask.objects.get().task_type == TaskType.LABEL_SCAN

    def test_la_tache_appartient_a_l_appelant(self, ai_enabled, active_user):
        scan(client_for(active_user))

        assert AsyncTask.objects.get().user == active_user

    def test_les_images_ne_survivent_pas_a_l_appel(self, ai_enabled, active_user, monkeypatch):
        from django.core.cache import cache

        from ai.services import images as image_store

        deposees: list[str] = []
        original = image_store.stash

        def spy(images):
            keys = original(images)
            deposees.extend(keys)
            return keys

        monkeypatch.setattr(image_store, "stash", spy)
        scan(client_for(active_user))

        assert deposees, "aucune image déposée : le test ne prouve rien"
        assert all(cache.get(key) is None for key in deposees)


class TestGuards:
    def test_l_ia_coupee_repond_503(self, ai_enabled, active_user):
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=False)

        response = scan(client_for(active_user))

        assert response.status_code == 503
        assert response.json()["code"] == "ai_disabled"

    def test_sans_photo_la_requete_est_refusee(self, ai_enabled, active_user):
        assert scan(client_for(active_user), []).status_code == 400

    def test_un_fichier_qui_n_est_pas_une_image(self, ai_enabled, active_user):
        upload = SimpleUploadedFile("doc.pdf", b"%PDF-1.4", content_type="application/pdf")

        assert scan(client_for(active_user), [upload]).status_code == 400

    def test_un_appel_anonyme_est_refuse(self, ai_enabled, db):
        assert scan(APIClient()).status_code == 401

    def test_un_compte_suspendu_est_refuse(self, ai_enabled, db):
        suspendu = User.objects.create_user(
            username="suspendu", password="un-mot-de-passe-solide-1", status=UserStatus.SUSPENDED
        )

        assert scan(client_for(suspendu)).status_code == 401
