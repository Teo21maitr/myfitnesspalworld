"""Endpoints des photos de progression (spec 04 §15, spec 05 §10).

Deux règles au-delà des formes de réponse : la **clé de stockage ne sort
jamais** — non devinable, elle est de fait un secret d'accès — et un partage
`progress`, qui ouvre bien les courbes d'un ami, **n'ouvre pas ses photos**
(spec 01 §20).
"""

import io
from datetime import date

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from progress.models import PhotoType, ProgressPhoto, ProgressPhotoGroup

pytestmark = pytest.mark.django_db

PHOTOS_URL = reverse("api-v1:progress:photo-list")
TODAY = date(2026, 8, 26)


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def upload(jpeg: bytes, name: str = "photo.jpg") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, jpeg, content_type="image/jpeg")


def send(client, jpeg, *, types=None, count=1, day=TODAY, **extra):
    payload = {
        "date": day.isoformat(),
        "photos": [upload(jpeg) for _ in range(count)],
        **extra,
    }
    if types:
        payload["photo_types"] = types
    return client.post(PHOTOS_URL, payload, format="multipart")


class TestUpload:
    def test_une_photo_est_enregistree(self, auth_client, fake_storage, jpeg_bytes):
        response = send(auth_client, jpeg_bytes, types=["front"])

        assert response.status_code == 201
        assert response.data["date"] == TODAY.isoformat()
        assert len(response.data["photos"]) == 1
        assert response.data["photos"][0]["photo_type"] == "front"
        assert fake_storage.count() == 1

    def test_les_quatre_angles_tiennent_dans_un_envoi(self, auth_client, fake_storage, jpeg_bytes):
        response = send(auth_client, jpeg_bytes, count=4, types=["front", "side", "back", "other"])

        assert response.status_code == 201
        assert [photo["photo_type"] for photo in response.data["photos"]] == [
            "back",
            "front",
            "other",
            "side",
        ]

    def test_un_cinquieme_fichier_est_refuse(self, auth_client, fake_storage, jpeg_bytes):
        response = send(auth_client, jpeg_bytes, count=5)

        assert response.status_code == 400
        assert fake_storage.count() == 0

    def test_un_angle_absent_vaut_autre(self, auth_client, fake_storage, jpeg_bytes):
        """La photo compte plus que son étiquette, et l'étiquette se corrige."""
        response = send(auth_client, jpeg_bytes)

        assert response.data["photos"][0]["photo_type"] == PhotoType.OTHER

    def test_une_seconde_date_complete_le_groupe(self, auth_client, fake_storage, jpeg_bytes):
        """On revient ajouter le profil après la face, sans tout remplacer."""
        send(auth_client, jpeg_bytes, types=["front"])
        response = send(auth_client, jpeg_bytes, types=["side"])

        assert response.status_code == 201
        assert len(response.data["photos"]) == 2
        assert ProgressPhotoGroup.objects.count() == 1

    def test_le_poids_du_jour_est_recopie(self, auth_client, fake_storage, jpeg_bytes):
        response = send(auth_client, jpeg_bytes, weight_kg_snapshot="78.40")

        assert response.data["weight_kg_snapshot"] == "78.40"

    def test_un_fichier_qui_n_est_pas_une_image_est_refuse(self, auth_client, fake_storage):
        response = auth_client.post(
            PHOTOS_URL,
            {
                "date": TODAY.isoformat(),
                "photos": [SimpleUploadedFile("x.jpg", b"pas une image", "image/jpeg")],
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert fake_storage.count() == 0

    def test_sans_stockage_configure_la_reponse_est_503(self, auth_client, settings, jpeg_bytes):
        """Fonctionnalité non branchée, pas panne : le reste continue."""
        settings.S3_BUCKET_NAME = ""

        response = send(auth_client, jpeg_bytes)

        assert response.status_code == 503
        assert response.data["code"] == "storage_unavailable"

    def test_l_image_stockee_est_reencodee(self, auth_client, fake_storage, jpeg_bytes):
        send(auth_client, jpeg_bytes)

        stored = next(iter(fake_storage.objects.values()))
        with Image.open(io.BytesIO(stored)) as image:
            assert image.format == "JPEG"
            assert dict(image.getexif()) == {}


class TestTheKeyNeverLeaves:
    def test_la_reponse_porte_une_url_et_jamais_la_cle(self, auth_client, fake_storage, jpeg_bytes):
        response = send(auth_client, jpeg_bytes)

        photo = response.data["photos"][0]
        key = ProgressPhoto.objects.get().storage_key

        assert photo["url"].startswith("https://seau.test/")
        assert "storage_key" not in photo
        assert key not in str(response.data).replace(photo["url"], "")

    def test_la_liste_non_plus(self, auth_client, fake_storage, jpeg_bytes):
        send(auth_client, jpeg_bytes)

        response = auth_client.get(PHOTOS_URL)

        assert "storage_key" not in str(response.data)


class TestReadAndPatch:
    def test_la_liste_est_antichronologique(self, auth_client, fake_storage, jpeg_bytes):
        send(auth_client, jpeg_bytes, day=date(2026, 8, 20))
        send(auth_client, jpeg_bytes, day=date(2026, 8, 26))

        response = auth_client.get(PHOTOS_URL)

        assert [row["date"] for row in response.data["results"]] == ["2026-08-26", "2026-08-20"]

    def test_seules_les_metadonnees_se_modifient(self, auth_client, fake_storage, jpeg_bytes):
        created = send(auth_client, jpeg_bytes)
        url = reverse("api-v1:progress:photo-detail", args=[created.data["id"]])

        response = auth_client.patch(url, {"notes": "Fin de cycle"}, format="json")

        assert response.status_code == 200
        assert response.data["notes"] == "Fin de cycle"
        assert len(response.data["photos"]) == 1


class TestDeletion:
    def test_supprimer_une_photo_la_retire_du_stockage(self, auth_client, fake_storage, jpeg_bytes):
        created = send(auth_client, jpeg_bytes, count=2)
        group_id = created.data["id"]
        photo_id = created.data["photos"][0]["id"]

        response = auth_client.delete(
            reverse("api-v1:progress:photo-file", args=[group_id, photo_id])
        )

        assert response.status_code == 204
        assert fake_storage.count() == 1

    def test_supprimer_le_groupe_retire_tout(self, auth_client, fake_storage, jpeg_bytes):
        created = send(auth_client, jpeg_bytes, count=3)

        response = auth_client.delete(
            reverse("api-v1:progress:photo-detail", args=[created.data["id"]])
        )

        assert response.status_code == 204
        assert fake_storage.count() == 0


class TestPermissions:
    def test_un_anonyme_est_refuse(self, api_client):
        assert api_client.get(PHOTOS_URL).status_code == 401

    def test_un_compte_suspendu_est_refuse(self, active_user, fake_storage):
        client = client_for(active_user)
        active_user.status = UserStatus.SUSPENDED
        active_user.save(update_fields=["status"])

        assert client.get(PHOTOS_URL).status_code == 401

    def test_on_ne_voit_que_ses_propres_photos(
        self, auth_client, other_user, fake_storage, jpeg_bytes
    ):
        send(client_for(other_user), jpeg_bytes)

        assert auth_client.get(PHOTOS_URL).data["count"] == 0

    def test_le_groupe_d_un_autre_repond_404(
        self, auth_client, other_user, fake_storage, jpeg_bytes
    ):
        created = send(client_for(other_user), jpeg_bytes)
        url = reverse("api-v1:progress:photo-detail", args=[created.data["id"]])

        assert auth_client.get(url).status_code == 404
        assert auth_client.delete(url).status_code == 404

    def test_la_photo_d_un_autre_repond_404(
        self, auth_client, other_user, fake_storage, jpeg_bytes
    ):
        created = send(client_for(other_user), jpeg_bytes)
        url = reverse(
            "api-v1:progress:photo-file",
            args=[created.data["id"], created.data["photos"][0]["id"]],
        )

        assert auth_client.delete(url).status_code == 404
        assert fake_storage.count() == 1


class TestPhotosAreNeverShared:
    def test_aucune_route_partagee_n_expose_les_photos(self, active_user, other_user):
        """Un partage `progress` ouvre les courbes et les pesées, pas les photos.

        Rien ne le vérifiait : l'absence de route est une décision, et une
        décision qu'aucun test ne tient finit par se perdre.
        """
        from django.urls import NoReverseMatch

        with pytest.raises(NoReverseMatch):
            reverse("api-v1:shared:progress-photos")

    def test_le_type_photo_n_existe_pas_dans_les_partages(self):
        from social.models import ResourceType

        assert not any("photo" in value for value in ResourceType.values)

    def test_un_ami_avec_un_partage_progress_ne_voit_pas_les_photos(
        self, active_user, other_user, fake_storage, jpeg_bytes
    ):
        from social.models import ResourceType, SharePermission, VisibilityType
        from social.services import friends as friends_service

        request = friends_service.send_request(from_user=active_user, to_user=other_user)
        friends_service.accept(request=request, user=other_user)
        SharePermission.objects.create(
            owner=active_user,
            target_user=other_user,
            resource_type=ResourceType.PROGRESS,
            visibility_type=VisibilityType.SPECIFIC_USER,
        )
        send(client_for(active_user), jpeg_bytes)

        # La courbe s'ouvre…
        charts = client_for(other_user).get(
            reverse("api-v1:shared:progress-charts"), {"user_id": active_user.id}
        )
        assert charts.status_code == 200

        # …mais les photos restent celles de leur propriétaire.
        assert client_for(other_user).get(PHOTOS_URL).data["count"] == 0
