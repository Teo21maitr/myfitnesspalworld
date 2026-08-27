"""Suivi des tâches longues (spec 04 §9, spec 05 §12)."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from common.models import AsyncTask, TaskStatus, TaskType
from common.tasks import purge_expired_tasks

pytestmark = pytest.mark.django_db


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


def url_for(task: AsyncTask) -> str:
    return reverse("api-v1:task-detail", args=[task.pk])


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def task(active_user) -> AsyncTask:
    return AsyncTask.objects.create(
        user=active_user,
        task_type=TaskType.MEAL_SCAN,
        status=TaskStatus.PROCESSING,
        progress=30,
    )


class TestOwnership:
    """Une tâche appartient à quelqu'un : c'est la raison d'être de la table."""

    def test_on_lit_sa_propre_tache(self, active_user, task):
        response = client_for(active_user).get(url_for(task))

        assert response.status_code == 200
        assert response.json() == {
            "id": str(task.pk),
            "task_type": TaskType.MEAL_SCAN,
            "status": TaskStatus.PROCESSING,
            "progress": 30,
            "result": None,
            "error": None,
            "created_at": response.json()["created_at"],
        }

    def test_la_tache_d_un_autre_repond_404(self, other_user, task):
        """404 et non 403 : confirmer l'existence renseignerait déjà."""
        assert client_for(other_user).get(url_for(task)).status_code == 404

    def test_un_appel_anonyme_est_refuse(self, task):
        assert APIClient().get(url_for(task)).status_code == 401

    def test_un_compte_suspendu_est_refuse(self, active_user, task):
        active_user.status = UserStatus.SUSPENDED
        active_user.save(update_fields=["status"])

        assert client_for(active_user).get(url_for(task)).status_code == 401

    def test_un_identifiant_inconnu_repond_404(self, active_user):
        url = reverse("api-v1:task-detail", args=["00000000-0000-0000-0000-000000000000"])

        assert client_for(active_user).get(url).status_code == 404


class TestExpiry:
    def test_une_tache_expiree_est_traitee_comme_absente(self, active_user, task):
        task.expires_at = timezone.now() - timedelta(seconds=1)
        task.save(update_fields=["expires_at"])

        assert client_for(active_user).get(url_for(task)).status_code == 404

    def test_une_tache_encore_valide_reste_lisible(self, active_user, task):
        task.expires_at = timezone.now() + timedelta(hours=1)
        task.save(update_fields=["expires_at"])

        assert client_for(active_user).get(url_for(task)).status_code == 200

    def test_le_nettoyage_supprime_les_taches_expirees(self, active_user, task):
        expired = AsyncTask.objects.create(
            user=active_user,
            task_type=TaskType.MEAL_SCAN,
            expires_at=timezone.now() - timedelta(days=1),
        )

        assert purge_expired_tasks() == 1
        assert not AsyncTask.objects.filter(pk=expired.pk).exists()
        assert AsyncTask.objects.filter(pk=task.pk).exists()

    def test_le_nettoyage_epargne_les_taches_sans_echeance(self, active_user, task):
        assert purge_expired_tasks() == 0
        assert AsyncTask.objects.filter(pk=task.pk).exists()


class TestResult:
    def test_le_resultat_est_renvoye_une_fois_la_tache_terminee(self, active_user, task):
        task.status = TaskStatus.SUCCESS
        task.progress = 100
        task.result = {"suggestions": []}
        task.save(update_fields=["status", "progress", "result"])

        payload = client_for(active_user).get(url_for(task)).json()

        assert payload["status"] == TaskStatus.SUCCESS
        assert payload["result"] == {"suggestions": []}

    def test_une_tache_echouee_porte_un_message(self, active_user, task):
        task.status = TaskStatus.FAILED
        task.error = "Le fournisseur d'IA est injoignable."
        task.save(update_fields=["status", "error"])

        payload = client_for(active_user).get(url_for(task)).json()

        assert payload["error"] == "Le fournisseur d'IA est injoignable."
        assert payload["result"] is None
