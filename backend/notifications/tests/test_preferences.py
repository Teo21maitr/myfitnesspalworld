"""Préférences de notification (spec 01 §24, spec 03 §11).

**Une préférence absente n'est pas une préférence.** Un compte qui n'a jamais
ouvert ses réglages n'a aucune ligne en base ; si chaque appelant décidait
lui-même du défaut, la réponse à « le canal email est-il actif ? » dépendrait de
qui pose la question.
"""

import pytest

from notifications.models import EventType, Notification, NotificationPreference
from notifications.services import dispatch

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(db):
    from accounts.models import User, UserStatus

    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


class TestDefaults:
    def test_un_compte_sans_ligne_a_les_six_types(self, active_user):
        """Toujours les six clés : l'appelant n'a pas à distinguer l'absence."""
        preferences = dispatch.preferences_for(active_user)

        assert set(preferences) == set(EventType.values)
        assert not NotificationPreference.objects.filter(user=active_user).exists()

    def test_un_rappel_ne_part_pas_par_email_par_defaut(self, active_user):
        """Un rappel quotidien par email devient du bruit qu'on filtre."""
        preferences = dispatch.preferences_for(active_user)

        assert preferences[EventType.MEAL_REMINDER].in_app
        assert not preferences[EventType.MEAL_REMINDER].email

    def test_un_evenement_rare_part_aussi_par_email(self, active_user):
        preferences = dispatch.preferences_for(active_user)

        assert preferences[EventType.FRIEND_REQUEST].email

    def test_aucun_canal_push_n_est_actif(self, active_user):
        """La colonne existe (spec 03 §11) ; aucun canal ne la lit encore."""
        preferences = dispatch.preferences_for(active_user)

        assert not any(channels.push for channels in preferences.values())


class TestStoredPreferences:
    def test_une_ligne_remplace_le_defaut(self, active_user):
        NotificationPreference.objects.create(
            user=active_user,
            event_type=EventType.MEAL_REMINDER,
            in_app_enabled=False,
            email_enabled=True,
        )

        preferences = dispatch.preferences_for(active_user)

        assert not preferences[EventType.MEAL_REMINDER].in_app
        assert preferences[EventType.MEAL_REMINDER].email

    def test_couper_un_type_ne_coupe_pas_les_autres(self, active_user):
        NotificationPreference.objects.create(
            user=active_user, event_type=EventType.MEAL_REMINDER, in_app_enabled=False
        )

        preferences = dispatch.preferences_for(active_user)

        assert not preferences[EventType.MEAL_REMINDER].in_app
        assert preferences[EventType.WEIGH_IN_REMINDER].in_app

    def test_les_preferences_d_un_autre_compte_ne_comptent_pas(self, active_user, other_user):
        NotificationPreference.objects.create(
            user=other_user, event_type=EventType.MEAL_REMINDER, in_app_enabled=False
        )

        assert dispatch.preferences_for(active_user)[EventType.MEAL_REMINDER].in_app


class TestNotify:
    def test_un_canal_coupe_ne_cree_rien(self, active_user):
        NotificationPreference.objects.create(
            user=active_user, event_type=EventType.FRIEND_REQUEST, in_app_enabled=False
        )

        created = dispatch.notify(
            active_user, event_type=EventType.FRIEND_REQUEST, title="Demande d'ami"
        )

        assert created is None
        assert not Notification.objects.exists()

    def test_l_email_part_quand_le_canal_est_actif(self, active_user, mailoutbox):
        active_user.email = "teo@example.com"
        active_user.save(update_fields=["email"])

        dispatch.notify(active_user, event_type=EventType.FRIEND_REQUEST, title="Demande d'ami")

        assert len(mailoutbox) == 1
        assert mailoutbox[0].subject == "Demande d'ami"

    def test_sans_adresse_aucun_email_ne_part(self, active_user, mailoutbox):
        """L'email est facultatif dans ce projet : son absence n'est pas une erreur."""
        assert not active_user.email

        created = dispatch.notify(
            active_user, event_type=EventType.FRIEND_REQUEST, title="Demande d'ami"
        )

        assert created is not None
        assert mailoutbox == []

    def test_un_rappel_ne_declenche_pas_d_email(self, active_user, mailoutbox):
        active_user.email = "teo@example.com"
        active_user.save(update_fields=["email"])

        dispatch.notify(active_user, event_type=EventType.WEIGH_IN_REMINDER, title="Pesée")

        assert mailoutbox == []

    def test_le_compteur_ne_voit_que_les_siennes(self, active_user, other_user):
        dispatch.notify(active_user, event_type=EventType.FRIEND_REQUEST, title="A")
        dispatch.notify(other_user, event_type=EventType.FRIEND_REQUEST, title="B")

        assert dispatch.unread_count(active_user) == 1
