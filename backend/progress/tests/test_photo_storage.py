"""Le fichier survit à la ligne (spec 01 §20, spec 05 §10-§11).

Le piège de l'étape. Supprimer une photo, c'est supprimer une ligne : c'est
facile, ça paraît complet, l'écran se met correctement à jour. Pendant ce temps
l'objet reste dans le seau, pour toujours — et la « suppression définitive » que
promet la spec 01 §20 est un mensonge que rien ne signale.

> **Ce qu'on supprime doit disparaître du stockage, pas seulement de la base.**

Trois chemins y mènent : une photo, un groupe, un compte. Le troisième est le
plus facile à oublier, parce que `user.delete()` a l'air de tout emporter.

Le client en mémoire n'est pas un raccourci : il applique les mêmes appels que
`boto3`, et permet de **compter ce qui reste**.
"""

from datetime import date
from decimal import Decimal

import pytest

from accounts.models import User, UserStatus
from progress.models import PhotoType, ProgressPhoto, ProgressPhotoGroup
from progress.services import photo_storage
from progress.services import photos as photos_service

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 26)


def add_photo(group: ProgressPhotoGroup, photo_type=PhotoType.FRONT) -> ProgressPhoto:
    key = photo_storage.store(b"des octets", content_type="image/jpeg")
    return ProgressPhoto.objects.create(
        group=group, photo_type=photo_type, storage_key=key, mime_type="image/jpeg", size_bytes=10
    )


@pytest.fixture
def group(active_user) -> ProgressPhotoGroup:
    return ProgressPhotoGroup.objects.create(user=active_user, date=TODAY)


class TestDeletionReachesTheStore:
    def test_supprimer_une_photo_supprime_son_objet(self, fake_storage, group):
        photo = add_photo(group)
        assert fake_storage.count() == 1

        photos_service.delete_photo(photo)

        assert fake_storage.count() == 0
        assert not ProgressPhoto.objects.filter(pk=photo.pk).exists()

    def test_supprimer_un_groupe_supprime_tous_ses_objets(self, fake_storage, group):
        add_photo(group, PhotoType.FRONT)
        add_photo(group, PhotoType.SIDE)
        add_photo(group, PhotoType.BACK)
        assert fake_storage.count() == 3

        photos_service.delete_group(group)

        assert fake_storage.count() == 0
        assert not ProgressPhotoGroup.objects.filter(pk=group.pk).exists()

    def test_supprimer_son_compte_supprime_tous_ses_objets(self, fake_storage, active_user, group):
        """`user.delete()` emporte les lignes en cascade, jamais les fichiers.

        D'où l'ordre : relever les clés, laisser la base tomber, purger. Le
        parcours complet passe par l'API et vit dans les tests de compte.
        """
        add_photo(group, PhotoType.FRONT)
        add_photo(group, PhotoType.SIDE)
        autre_jour = ProgressPhotoGroup.objects.create(
            user=active_user, date=date(2026, 8, 20), weight_kg_snapshot=Decimal("80")
        )
        add_photo(autre_jour)
        assert fake_storage.count() == 3

        keys = photos_service.keys_of(active_user)
        active_user.delete()
        photos_service.purge(keys)

        assert fake_storage.count() == 0

    def test_les_objets_d_un_autre_compte_ne_sont_pas_releves(
        self, fake_storage, active_user, group
    ):
        add_photo(group)
        autre = User.objects.create_user(
            username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
        )
        add_photo(ProgressPhotoGroup.objects.create(user=autre, date=TODAY))

        assert len(photos_service.keys_of(active_user)) == 1


class TestOrder:
    def test_une_transaction_en_echec_ne_supprime_aucun_objet(
        self, fake_storage, group, monkeypatch
    ):
        """Supprimer un objet est irréversible : jamais avant d'être sûr.

        Une ligne qui pointe vers un fichier disparu est l'erreur symétrique,
        et tout aussi invisible.
        """
        add_photo(group)

        def boom(*args, **kwargs):
            raise RuntimeError("la base a lâché")

        monkeypatch.setattr(ProgressPhotoGroup, "delete", boom)

        with pytest.raises(RuntimeError):
            photos_service.delete_group(group)

        assert fake_storage.count() == 1


class TestTheKey:
    def test_deux_envois_du_meme_fichier_donnent_deux_cles(self, fake_storage):
        first = photo_storage.store(b"identique", content_type="image/jpeg")
        second = photo_storage.store(b"identique", content_type="image/jpeg")

        assert first != second

    def test_la_cle_ne_dit_rien_de_son_proprietaire(self, fake_storage, active_user, group):
        """Un chemin qui nomme son propriétaire le trahit sans qu'on l'ouvre.

        L'assertion porte sur la **forme** plutôt que sur l'absence de tel ou
        tel fragment : un identifiant à un chiffre se retrouverait par hasard
        dans n'importe quel hexadécimal. Une clé qui n'est qu'un préfixe et
        trente-deux caractères aléatoires ne peut rien porter d'autre.
        """
        photo = add_photo(group)

        prefix, _, suffix = photo.storage_key.partition("/")

        assert prefix == photo_storage.KEY_PREFIX
        assert len(suffix) == 32
        assert all(character in "0123456789abcdef" for character in suffix)
        assert active_user.username not in photo.storage_key

    def test_la_cle_n_est_pas_sequentielle(self, fake_storage):
        cles = {photo_storage.store(b"x", content_type="image/jpeg") for _ in range(20)}

        assert len(cles) == 20


class TestTheSignedUrl:
    def test_une_url_signee_porte_une_expiration(self, fake_storage, group):
        photo = add_photo(group)

        photo_storage.signed_url(photo.storage_key, seconds=42)

        assert fake_storage.last_expiry == 42

    def test_la_duree_par_defaut_est_courte(self, fake_storage, group, settings):
        """Une URL émise vaut jusqu'à son expiration, même photo supprimée."""
        photo = add_photo(group)

        photo_storage.signed_url(photo.storage_key)

        assert fake_storage.last_expiry == settings.PROGRESS_PHOTO_URL_TTL
        assert settings.PROGRESS_PHOTO_URL_TTL <= 900


class TestTheUrlPointsWhereTheBrowserCanGo:
    """Le backend et le stockage peuvent se parler par un réseau privé.

    Le navigateur, lui, ne le connaît pas. Sous Docker, le conteneur joint
    MinIO par `http://minio:9000` — un nom qui n'existe nulle part ailleurs.
    Une URL signée pour cette adresse ne s'ouvre pas, et l'image reste vide
    sans que rien ne le signale.
    """

    def test_l_url_signee_porte_l_adresse_publique(self, settings, group):
        settings.S3_BUCKET_NAME = "seau-de-test"
        settings.S3_ENDPOINT_URL = "http://minio:9000"
        settings.S3_PUBLIC_ENDPOINT_URL = "http://localhost:9002"

        photo_storage.set_client(None)
        try:
            url = photo_storage.signed_url("progress-photos/abc")
        finally:
            photo_storage.set_client(None)

        assert url.startswith("http://localhost:9002/")
        assert "minio:9000" not in url

    def test_sans_adresse_publique_l_endpoint_sert_aux_deux(self, settings):
        settings.S3_BUCKET_NAME = "seau-de-test"
        settings.S3_ENDPOINT_URL = "http://stockage.example"
        settings.S3_PUBLIC_ENDPOINT_URL = "http://stockage.example"

        photo_storage.set_client(None)
        url = photo_storage.signed_url("progress-photos/abc")

        assert url.startswith("http://stockage.example/")

    def test_l_url_reste_signee_pour_l_hote_qu_elle_porte(self, settings):
        """SigV4 signe l'en-tête `Host` : réécrire l'hôte après coup casserait
        la signature. C'est l'adresse publique qu'il faut signer d'emblée."""
        settings.S3_BUCKET_NAME = "seau-de-test"
        settings.S3_ENDPOINT_URL = "http://minio:9000"
        settings.S3_PUBLIC_ENDPOINT_URL = "http://localhost:9002"

        photo_storage.set_client(None)
        url = photo_storage.signed_url("progress-photos/abc")

        assert "X-Amz-Signature" in url
        assert "X-Amz-Credential" in url
