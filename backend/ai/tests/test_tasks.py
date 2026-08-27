"""Tâche d'analyse : cycle de vie et sort des images (spec 07 §5, §9)."""

import pytest
from django.core.cache import cache

from ai.providers import AIProviderUnavailable
from ai.services import images as image_store
from ai.tasks import GENERIC_FAILURE, analyze_meal_task
from common.models import AsyncTask, TaskStatus, TaskType

from .conftest import StubProvider

pytestmark = pytest.mark.django_db

VALID = {
    "items": [
        {
            "label": "poulet",
            "estimated_quantity": 150,
            "unit": "g",
            "confidence": 0.8,
            "alternatives": [],
        }
    ]
}


@pytest.fixture
def task(active_user) -> AsyncTask:
    return AsyncTask.objects.create(user=active_user, task_type=TaskType.MEAL_SCAN)


@pytest.fixture
def use_provider(monkeypatch):
    def install(provider):
        monkeypatch.setattr("ai.services.ai_service.get_provider", lambda: provider)
        return provider

    return install


class TestImagesDoNotSurvive:
    """La photo ne survit pas au traitement, quel qu'en soit l'issue."""

    def test_apres_une_analyse_reussie(self, task, image_part, use_provider, chicken, settings):
        settings.AI_MEAL_SCAN_MODEL = "modele-de-test"
        use_provider(StubProvider(payload=VALID))
        keys = image_store.stash([image_part])

        analyze_meal_task(str(task.pk), keys)

        assert all(cache.get(key) is None for key in keys)

    def test_apres_une_panne_du_fournisseur(self, task, image_part, use_provider):
        use_provider(StubProvider(error=AIProviderUnavailable("Injoignable.")))
        keys = image_store.stash([image_part])

        analyze_meal_task(str(task.pk), keys)

        assert all(cache.get(key) is None for key in keys)

    def test_apres_une_erreur_inattendue(self, task, image_part, use_provider):
        use_provider(StubProvider(error=RuntimeError("boum")))
        keys = image_store.stash([image_part])

        analyze_meal_task(str(task.pk), keys)

        assert all(cache.get(key) is None for key in keys)

    def test_quand_la_tache_a_disparu(self, image_part, use_provider):
        """Un compte supprimé ne doit pas laisser sa photo derrière lui."""
        keys = image_store.stash([image_part])

        analyze_meal_task("00000000-0000-0000-0000-000000000000", keys)

        assert all(cache.get(key) is None for key in keys)


class TestOutcome:
    def test_une_analyse_reussie_range_les_suggestions(
        self, task, image_part, use_provider, chicken, settings
    ):
        settings.AI_MEAL_SCAN_MODEL = "modele-de-test"
        use_provider(StubProvider(payload=VALID))

        analyze_meal_task(str(task.pk), image_store.stash([image_part]))

        task.refresh_from_db()
        assert task.status == TaskStatus.SUCCESS
        assert task.progress == 100
        assert task.error is None
        assert task.result["suggestions"][0]["candidates"][0]["id"] == chicken.pk

    def test_une_panne_donne_un_message_lisible(self, task, image_part, use_provider):
        use_provider(StubProvider(error=AIProviderUnavailable("Le fournisseur est saturé.")))

        analyze_meal_task(str(task.pk), image_store.stash([image_part]))

        task.refresh_from_db()
        assert task.status == TaskStatus.FAILED
        assert task.error == "Le fournisseur est saturé."
        assert task.result is None

    def test_une_erreur_inattendue_ne_fuite_pas(self, task, image_part, use_provider):
        use_provider(StubProvider(error=RuntimeError("connexion postgres://user:motdepasse@db")))

        analyze_meal_task(str(task.pk), image_store.stash([image_part]))

        task.refresh_from_db()
        assert task.status == TaskStatus.FAILED
        assert task.error == GENERIC_FAILURE
        assert "motdepasse" not in task.error

    def test_des_images_expirees_donnent_un_echec_explicite(self, task, image_part):
        keys = image_store.stash([image_part])
        image_store.discard(keys)

        analyze_meal_task(str(task.pk), keys)

        task.refresh_from_db()
        assert task.status == TaskStatus.FAILED
        assert "expiré" in task.error

    def test_une_photo_sans_aliment_reussit_a_vide(self, task, image_part, use_provider, settings):
        """Ne rien reconnaître n'est pas une panne (spec 07 §5)."""
        settings.AI_MEAL_SCAN_MODEL = "modele-de-test"
        use_provider(StubProvider(payload={"items": []}))

        analyze_meal_task(str(task.pk), image_store.stash([image_part]))

        task.refresh_from_db()
        assert task.status == TaskStatus.SUCCESS
        assert task.result == {"suggestions": []}
