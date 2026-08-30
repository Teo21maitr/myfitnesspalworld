"""Configuration pytest partagée."""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isole les tests du throttling DRF, qui s'appuie sur le cache.

    Sans cela, les tentatives de connexion s'accumuleraient d'un test à
    l'autre et déclencheraient une 429 fortuite.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def active_user(db):
    """Utilisateur ACTIVE prêt à être authentifié."""
    from accounts.models import User, UserStatus

    return User.objects.create_user(
        username="teo",
        password="motdepasse-de-test-123",
        status=UserStatus.ACTIVE,
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(active_user):
    """Client authentifié par cookies, comme le fait le navigateur.

    Instancie son propre client plutôt que de réutiliser `api_client` : les
    tests qui comparent deux appareils ont besoin de deux clients distincts.
    """
    from django.conf import settings
    from rest_framework.test import APIClient

    from accounts.services.sessions import build_refresh_token

    client = APIClient()
    refresh = build_refresh_token(active_user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


class FakeS3:
    """Client S3 en mémoire, pour les tests.

    Les paramètres portent les noms de `boto3` — majuscules comprises — pour
    que le service soit appelé exactement comme il appellera le vrai client.
    Ce qui compte ici est de pouvoir **compter ce qui reste**.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.last_expiry: int | None = None

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body
        return {}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.last_expiry = ExpiresIn
        return f"https://seau.test/{Params['Key']}?expires={ExpiresIn}"

    def delete_objects(self, *, Bucket, Delete):
        for entry in Delete["Objects"]:
            self.objects.pop(entry["Key"], None)
        return {}

    def count(self) -> int:
        return len(self.objects)


@pytest.fixture
def fake_storage(settings):
    """Remplace le stockage objet, et le rend inspectable."""
    from progress.services import photo_storage

    settings.S3_BUCKET_NAME = "seau-de-test"
    settings.S3_ENDPOINT_URL = "http://stockage.test"

    client = FakeS3()
    photo_storage.set_client(client)
    yield client
    photo_storage.set_client(None)


@pytest.fixture
def jpeg_bytes() -> bytes:
    """Un vrai JPEG minuscule, que Pillow sait rouvrir."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (90, 30, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()
