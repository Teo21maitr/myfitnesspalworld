"""Abstraction de service IA et journalisation (spec 07 §2, §10)."""

import pytest

from ai.models import AILogStatus, AITaskLog
from ai.providers import AIProviderUnavailable, AIResponseUnusable
from ai.schemas import MEAL_SCAN_JSON_SCHEMA
from ai.services.ai_service import AIService
from common.models import TaskType

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


def analyze(user, provider, images):
    return AIService(provider=provider).analyze_meal(
        user=user, images=images, model="modele-de-test"
    )


class TestCall:
    def test_le_fournisseur_recoit_les_images_et_le_schema(self, active_user, image_part):
        provider = StubProvider(payload=VALID)

        analyze(active_user, provider, [image_part])

        call = provider.calls[0]
        assert call["images"] == (image_part,)
        assert call["schema"] is MEAL_SCAN_JSON_SCHEMA
        assert call["model"] == "modele-de-test"

    def test_la_consigne_interdit_les_valeurs_nutritionnelles(self, active_user, image_part):
        provider = StubProvider(payload=VALID)

        analyze(active_user, provider, [image_part])

        assert "JAMAIS de calories" in provider.calls[0]["system"]

    def test_les_aliments_detectes_sont_renvoyes(self, active_user, image_part):
        items = analyze(active_user, StubProvider(payload=VALID), [image_part])

        assert [item["label"] for item in items] == ["poulet"]


class TestLogging:
    def test_un_appel_reussi_laisse_une_trace_close(self, active_user, image_part):
        analyze(active_user, StubProvider(payload=VALID), [image_part])

        log = AITaskLog.objects.get()
        assert log.user == active_user
        assert log.task_type == TaskType.MEAL_SCAN
        assert log.status == AILogStatus.SUCCESS
        assert log.provider == "stub"
        assert log.model == "modele-de-test"
        assert log.output_summary == "1 aliment(s) détecté(s)"
        assert log.finished_at is not None
        assert log.duration_seconds is not None

    def test_la_trace_ne_contient_ni_image_ni_prompt(self, active_user, image_part):
        analyze(active_user, StubProvider(payload=VALID), [image_part])

        log = AITaskLog.objects.get()
        stored = " ".join(
            str(value)
            for value in (log.input_summary, log.output_summary, log.error_message)
            if value
        )
        # Le résumé décrit la forme de l'entrée, pas son contenu.
        assert log.input_summary == "1 image(s), 0 ko"
        assert "\xff\xd8" not in stored
        assert "identifie" not in stored.lower()

    def test_une_panne_est_tracee_puis_propagee(self, active_user, image_part):
        provider = StubProvider(error=AIProviderUnavailable("Le fournisseur d'IA est injoignable."))

        with pytest.raises(AIProviderUnavailable):
            analyze(active_user, provider, [image_part])

        log = AITaskLog.objects.get()
        assert log.status == AILogStatus.FAILED
        assert log.error_message == "Le fournisseur d'IA est injoignable."
        assert log.output_summary is None
        assert log.finished_at is not None

    def test_une_reponse_invalide_est_tracee_comme_un_echec(self, active_user, image_part):
        provider = StubProvider(payload={"items": [{"label": "poulet"}]})

        with pytest.raises(AIResponseUnusable):
            analyze(active_user, provider, [image_part])

        log = AITaskLog.objects.get()
        assert log.status == AILogStatus.FAILED
        assert "invalide" in log.error_message
