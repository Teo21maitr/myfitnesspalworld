"""Les événements sociaux produisent enfin une notification (spec 01 §24).

Jusqu'ici, une demande d'ami arrivait sans rien : la pastille de navigation
était le seul signal, et un partage reçu n'en avait aucun.
"""

import pytest
from django.db import transaction

from accounts.models import User, UserStatus
from notifications.models import EventType, Notification
from social.models import ResourceType
from social.services import friends as friends_service

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def alice(db) -> User:
    return User.objects.create_user(
        username="alice", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def bob(db) -> User:
    return User.objects.create_user(
        username="bob", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


class TestFriendRequests:
    def test_une_demande_notifie_son_destinataire(self, alice, bob):
        friends_service.send_request(from_user=alice, to_user=bob)

        notification = Notification.objects.get(user=bob)
        assert notification.event_type == EventType.FRIEND_REQUEST
        assert "alice" in notification.title
        assert notification.link == "/amis"

    def test_le_demandeur_n_est_pas_notifie_de_sa_propre_demande(self, alice, bob):
        friends_service.send_request(from_user=alice, to_user=bob)

        assert not Notification.objects.filter(user=alice).exists()

    def test_accepter_notifie_le_demandeur(self, alice, bob):
        request = friends_service.send_request(from_user=alice, to_user=bob)
        Notification.objects.all().delete()

        friends_service.accept(request=request, user=bob)

        notification = Notification.objects.get(user=alice)
        assert notification.event_type == EventType.FRIEND_ACCEPTED
        assert "bob" in notification.title

    def test_refuser_ne_notifie_personne(self, alice, bob):
        request = friends_service.send_request(from_user=alice, to_user=bob)
        Notification.objects.all().delete()

        friends_service.reject(request=request, user=bob)

        assert not Notification.objects.exists()

    def test_une_demande_qui_echoue_ne_notifie_personne(self, alice):
        """Émis après commit : rien ne part si l'écriture n'aboutit pas."""
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            friends_service.send_request(from_user=alice, to_user=alice)

        assert not Notification.objects.exists()

    def test_une_transaction_annulee_ne_notifie_personne(self, alice, bob):
        try:
            with transaction.atomic():
                friends_service.send_request(from_user=alice, to_user=bob)
                raise RuntimeError("la suite a échoué")
        except RuntimeError:
            pass

        assert not Notification.objects.exists()


class TestShares:
    def test_un_partage_nomme_notifie_son_destinataire(self, alice, bob):
        from django.conf import settings
        from rest_framework.test import APIClient

        from accounts.services.sessions import build_refresh_token

        request = friends_service.send_request(from_user=alice, to_user=bob)
        friends_service.accept(request=request, user=bob)
        Notification.objects.all().delete()

        client = APIClient()
        refresh = build_refresh_token(alice)
        client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
        client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)

        response = client.post(
            "/api/v1/shares/",
            {
                "resource_type": ResourceType.DIARY,
                "visibility": "specific_user",
                "target_user_id": bob.id,
            },
            format="json",
        )

        assert response.status_code == 201
        notification = Notification.objects.get(user=bob)
        assert notification.event_type == EventType.SHARE_RECEIVED
        assert notification.link == "/partages"

    def test_un_partage_a_tous_ne_notifie_personne(self, alice):
        """Il ne vise personne : il n'a personne à prévenir."""
        from django.conf import settings
        from rest_framework.test import APIClient

        from accounts.services.sessions import build_refresh_token

        client = APIClient()
        refresh = build_refresh_token(alice)
        client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
        client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)

        response = client.post(
            "/api/v1/shares/",
            {"resource_type": ResourceType.DIARY, "visibility": "app_users"},
            format="json",
        )

        assert response.status_code == 201
        assert not Notification.objects.exists()
