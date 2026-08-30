"""Les deux silences d'un rappel (spec 01 §24).

Le piège de l'étape. Un rappel a deux façons d'échouer, et **aucune ne lève
d'exception** :

- **partir deux fois** — l'utilisateur reçoit la même chose deux fois et se
  désabonne ; rien ne le signale ;
- **ne pas partir** — rien ne distingue « aucun rappel n'était dû » de « le
  rappel a été manqué ».

D'où l'idempotence **en base** : la notification est la preuve. Un verrou de
cache aurait expiré, disparu au redémarrage de Redis, et n'aurait été la source
de vérité de rien.
"""

from datetime import date, datetime, time, timedelta

import pytest
from django.utils import timezone

from notifications.models import EventType, Notification, Reminder, ReminderType
from notifications.services import reminders as reminders_service

pytestmark = pytest.mark.django_db

#: Un lundi, à huit heures pile.
MONDAY = date(2026, 8, 31)


def at(hour: int, minute: int = 0, day: date = MONDAY):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


@pytest.fixture
def other_user(db):
    from accounts.models import User, UserStatus

    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def reminder(active_user) -> Reminder:
    return Reminder.objects.create(
        user=active_user, reminder_type=ReminderType.WEIGH_IN, time=time(8, 0)
    )


class TestAReminderFiresExactlyOnce:
    """Le piège, des deux côtés."""

    def test_un_rappel_du_part(self, reminder, active_user):
        """Ne pas partir ne s'observe nulle part : ce test est le seul endroit."""
        sent = reminders_service.run(now=at(8, 2))

        assert sent == 1
        notification = Notification.objects.get(user=active_user)
        assert notification.event_type == EventType.WEIGH_IN_REMINDER
        assert notification.scheduled_on == MONDAY

    def test_deux_passages_ne_font_qu_une_notification(self, reminder, active_user):
        reminders_service.run(now=at(8, 2))
        reminders_service.run(now=at(8, 7))

        assert Notification.objects.filter(user=active_user).count() == 1

    def test_un_worker_relance_ne_rejoue_pas_la_journee(self, reminder, active_user):
        """Le cas que le verrou de cache aurait laissé passer."""
        for minute in (2, 7, 12, 17, 22):
            reminders_service.run(now=at(8, minute))

        assert Notification.objects.filter(user=active_user).count() == 1

    def test_le_lendemain_le_rappel_repart(self, reminder, active_user):
        reminders_service.run(now=at(8, 2))
        reminders_service.run(now=at(8, 2, MONDAY + timedelta(days=1)))

        assert Notification.objects.filter(user=active_user).count() == 2


class TestTheCatchUpWindow:
    """Un rappel manqué ne se rattrape pas indéfiniment."""

    def test_un_rappel_recent_est_rattrape(self, reminder, active_user):
        """Une interruption courte ne doit pas faire perdre le rappel."""
        sent = reminders_service.run(now=at(8, 45))

        assert sent == 1

    def test_un_rappel_trop_ancien_est_saute(self, reminder, active_user, caplog):
        """« Pense à te peser ce matin » à midi n'est plus un rappel."""
        with caplog.at_level("INFO"):
            sent = reminders_service.run(now=at(11, 30))

        assert sent == 0
        assert not Notification.objects.filter(user=active_user).exists()
        # Sauté, mais jamais en silence.
        assert any("hors fenêtre" in record.message for record in caplog.records)

    def test_un_rappel_a_venir_n_est_pas_anticipe(self, reminder, active_user):
        assert reminders_service.run(now=at(7, 30)) == 0
        assert not Notification.objects.filter(user=active_user).exists()

    def test_la_fenetre_est_courte(self):
        """Écrite et assumée : au-delà, un rappel devient du bruit."""
        assert timedelta(hours=2) >= reminders_service.CATCH_UP


class TestWhichRemindersAreDue:
    def test_un_rappel_desactive_ne_part_pas(self, reminder, active_user):
        reminder.enabled = False
        reminder.save(update_fields=["enabled"])

        assert reminders_service.run(now=at(8, 2)) == 0

    def test_un_jour_non_retenu_ne_declenche_rien(self, reminder, active_user):
        # Du lundi au vendredi seulement.
        reminder.days_of_week = [0, 1, 2, 3, 4]
        reminder.save(update_fields=["days_of_week"])

        samedi = MONDAY + timedelta(days=5)

        assert reminders_service.run(now=at(8, 2, samedi)) == 0

    def test_le_jour_retenu_declenche(self, reminder, active_user):
        reminder.days_of_week = [5]
        reminder.save(update_fields=["days_of_week"])

        samedi = MONDAY + timedelta(days=5)

        assert reminders_service.run(now=at(8, 2, samedi)) == 1

    def test_les_rappels_de_plusieurs_comptes_partent_tous(self, reminder, other_user):
        Reminder.objects.create(
            user=other_user, reminder_type=ReminderType.WEIGH_IN, time=time(8, 0)
        )

        assert reminders_service.run(now=at(8, 2)) == 2

    def test_chaque_type_a_son_evenement(self, active_user):
        Reminder.objects.create(user=active_user, reminder_type=ReminderType.MEAL, time=time(8, 0))
        Reminder.objects.create(user=active_user, reminder_type=ReminderType.PLAN, time=time(8, 0))

        reminders_service.run(now=at(8, 2))

        assert set(Notification.objects.values_list("event_type", flat=True)) == {
            EventType.MEAL_REMINDER,
            EventType.PLAN_REMINDER,
        }
