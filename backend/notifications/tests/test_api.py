"""Endpoints des notifications, préférences et rappels (spec 04 §19)."""

from datetime import time

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from notifications.models import EventType, Notification, NotificationPreference, Reminder
from notifications.services import dispatch

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api-v1:notifications:list")
READ_ALL_URL = reverse("api-v1:notifications:read-all")
PREFERENCES_URL = reverse("api-v1:notification-preferences:preferences")
REMINDERS_URL = reverse("api-v1:reminders:list")


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


def make(user, title="Demande d'ami", read=False) -> Notification:
    return Notification.objects.create(
        user=user, event_type=EventType.FRIEND_REQUEST, title=title, is_read=read
    )


class TestList:
    def test_la_liste_porte_le_compteur_de_non_lues(self, auth_client, active_user):
        make(active_user)
        make(active_user, title="Partage", read=True)

        response = auth_client.get(LIST_URL)

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert response.data["unread"] == 1

    def test_on_ne_voit_que_les_siennes(self, auth_client, other_user):
        make(other_user)

        assert auth_client.get(LIST_URL).data["count"] == 0

    def test_les_plus_recentes_d_abord(self, auth_client, active_user):
        make(active_user, title="Ancienne")
        make(active_user, title="Récente")

        titles = [row["title"] for row in auth_client.get(LIST_URL).data["results"]]

        assert titles == ["Récente", "Ancienne"]

    def test_les_rouages_de_l_idempotence_ne_sortent_pas(self, auth_client, active_user):
        """`reminder` et `scheduled_on` n'intéressent pas le lecteur."""
        make(active_user)

        row = auth_client.get(LIST_URL).data["results"][0]

        assert "reminder" not in row
        assert "scheduled_on" not in row


class TestMarkingRead:
    def test_marquer_une_notification_lue(self, auth_client, active_user):
        notification = make(active_user)

        response = auth_client.post(reverse("api-v1:notifications:read", args=[notification.pk]))

        assert response.status_code == 200
        assert response.data["is_read"] is True

    def test_celle_d_un_autre_repond_404(self, auth_client, other_user):
        notification = make(other_user)

        url = reverse("api-v1:notifications:read", args=[notification.pk])

        assert auth_client.post(url).status_code == 404
        notification.refresh_from_db()
        assert not notification.is_read

    def test_tout_marquer_lu_ne_touche_que_les_siennes(self, auth_client, active_user, other_user):
        make(active_user)
        make(active_user)
        etrangere = make(other_user)

        response = auth_client.post(READ_ALL_URL)

        assert response.data["updated"] == 2
        etrangere.refresh_from_db()
        assert not etrangere.is_read


class TestPreferences:
    def test_les_six_types_sortent_sans_aucune_ligne(self, auth_client, active_user):
        response = auth_client.get(PREFERENCES_URL)

        assert response.status_code == 200
        assert len(response.data["results"]) == len(EventType.values)
        assert not NotificationPreference.objects.exists()

    def test_le_push_est_rendu_mais_inactif(self, auth_client):
        """La colonne existe ; aucun canal ne la lit encore."""
        rows = auth_client.get(PREFERENCES_URL).data["results"]

        assert all(row["push_enabled"] is False for row in rows)

    def test_une_modification_partielle_est_acceptee(self, auth_client, active_user):
        response = auth_client.patch(
            PREFERENCES_URL,
            {
                "results": [
                    {
                        "event_type": EventType.MEAL_REMINDER,
                        "in_app_enabled": False,
                        "email_enabled": True,
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 200
        preferences = dispatch.preferences_for(active_user)
        assert not preferences[EventType.MEAL_REMINDER].in_app
        assert preferences[EventType.MEAL_REMINDER].email
        # Les autres types gardent leur défaut.
        assert preferences[EventType.WEIGH_IN_REMINDER].in_app

    def test_un_type_inconnu_est_refuse(self, auth_client):
        response = auth_client.patch(
            PREFERENCES_URL,
            {"results": [{"event_type": "zorglub", "in_app_enabled": True, "email_enabled": True}]},
            format="json",
        )

        assert response.status_code == 400


class TestReminders:
    def test_creer_un_rappel(self, auth_client, active_user):
        response = auth_client.post(
            REMINDERS_URL,
            {"reminder_type": "weigh_in", "time": "08:00", "days_of_week": [0, 1, 2, 3, 4]},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["days_of_week"] == [0, 1, 2, 3, 4]
        assert Reminder.objects.filter(user=active_user).count() == 1

    def test_un_second_envoi_du_meme_type_met_a_jour(self, auth_client, active_user):
        """« Un seul rappel par type » se règle, il ne se refuse pas."""
        auth_client.post(REMINDERS_URL, {"reminder_type": "meal", "time": "12:00"}, format="json")
        response = auth_client.post(
            REMINDERS_URL, {"reminder_type": "meal", "time": "13:30"}, format="json"
        )

        assert response.status_code == 200
        assert Reminder.objects.filter(user=active_user).count() == 1
        assert Reminder.objects.get(user=active_user).time == time(13, 30)

    def test_tous_les_jours_par_defaut(self, auth_client):
        response = auth_client.post(
            REMINDERS_URL, {"reminder_type": "plan", "time": "09:00"}, format="json"
        )

        assert response.data["days_of_week"] == [0, 1, 2, 3, 4, 5, 6]

    def test_une_liste_de_jours_vide_est_refusee(self, auth_client):
        """Un rappel qui ne part jamais se désactive, il ne se vide pas."""
        response = auth_client.post(
            REMINDERS_URL,
            {"reminder_type": "meal", "time": "12:00", "days_of_week": []},
            format="json",
        )

        assert response.status_code == 400

    def test_un_jour_hors_bornes_est_refuse(self, auth_client):
        response = auth_client.post(
            REMINDERS_URL,
            {"reminder_type": "meal", "time": "12:00", "days_of_week": [0, 7]},
            format="json",
        )

        assert response.status_code == 400

    def test_les_doublons_de_jours_sont_absorbes(self, auth_client):
        response = auth_client.post(
            REMINDERS_URL,
            {"reminder_type": "meal", "time": "12:00", "days_of_week": [2, 0, 2]},
            format="json",
        )

        assert response.data["days_of_week"] == [0, 2]

    def test_le_rappel_d_un_autre_repond_404(self, auth_client, other_user):
        reminder = Reminder.objects.create(user=other_user, reminder_type="meal", time=time(12, 0))
        url = reverse("api-v1:reminders:detail", args=[reminder.pk])

        assert auth_client.get(url).status_code == 404
        assert auth_client.delete(url).status_code == 404

    def test_supprimer_son_rappel(self, auth_client, active_user):
        reminder = Reminder.objects.create(user=active_user, reminder_type="meal", time=time(12, 0))

        response = auth_client.delete(reverse("api-v1:reminders:detail", args=[reminder.pk]))

        assert response.status_code == 204
        assert not Reminder.objects.exists()


class TestPermissions:
    @pytest.mark.parametrize("url", [LIST_URL, PREFERENCES_URL, REMINDERS_URL])
    def test_un_anonyme_est_refuse(self, api_client, url):
        assert api_client.get(url).status_code == 401

    def test_un_compte_suspendu_est_refuse(self, active_user):
        client = client_for(active_user)
        active_user.status = UserStatus.SUSPENDED
        active_user.save(update_fields=["status"])

        assert client.get(LIST_URL).status_code == 401
