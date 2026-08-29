"""Traduction des pannes du fournisseur en erreurs du projet.

Aucun test ne touche le réseau : ce qui compte ici est ce qui ressort d'une
erreur, pas ce qui l'a provoquée.
"""

import logging

import pytest

from ai.providers import AIProviderUnavailable, AIResponseUnusable, ImagePart
from ai.providers.anthropic import AnthropicProvider

SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
IMAGE = ImagePart(media_type="image/jpeg", data=b"\xff\xd8\xff\xe0")


def call(provider, model="modele-de-test"):
    return provider.structured_completion(
        model=model, system="s", prompt="p", schema=SCHEMA, images=(IMAGE,)
    )


class TestConfiguration:
    def test_sans_cle_l_appel_est_refuse_avant_le_reseau(self):
        with pytest.raises(AIProviderUnavailable, match="clé"):
            call(AnthropicProvider(api_key=""))

    def test_sans_modele_l_appel_est_refuse_avant_le_reseau(self):
        with pytest.raises(AIProviderUnavailable, match="modèle"):
            call(AnthropicProvider(api_key="sk-ant-factice"), model="")


class StatusError(Exception):
    """Imite `anthropic.APIStatusError` pour la journalisation."""

    def __init__(self, status_code: int, body: dict, request_id: str | None = None) -> None:
        super().__init__("refus")
        self.status_code = status_code
        self.body = body
        self.request_id = request_id


class TestDiagnosticLogging:
    """Ce qui est journalisé quand le fournisseur refuse.

    Le message rendu à l'utilisateur est volontairement générique. Sans trace,
    un schéma devenu invalide ressemble à n'importe quelle panne — c'est
    exactement ce qui s'est produit avec `maxItems`.
    """

    def test_une_requete_invalide_est_journalisee_avec_son_motif(self, caplog):
        from ai.providers.anthropic import _log_status_error

        erreur = StatusError(
            400,
            {"error": {"type": "invalid_request_error", "message": "maxItems is not supported"}},
            request_id="req_123",
        )

        with caplog.at_level(logging.WARNING):
            _log_status_error(erreur)

        assert "maxItems is not supported" in caplog.text
        assert "req_123" in caplog.text

    def test_les_autres_erreurs_ne_recopient_pas_leur_message(self, caplog):
        """Elles peuvent citer la charge utile, donc le repas de quelqu'un."""
        from ai.providers.anthropic import _log_status_error

        erreur = StatusError(
            413,
            {"error": {"type": "request_too_large", "message": "photo de mon dîner"}},
            request_id="req_456",
        )

        with caplog.at_level(logging.INFO):
            _log_status_error(erreur)

        assert "dîner" not in caplog.text
        assert "request_too_large" in caplog.text
        assert "413" in caplog.text

    def test_un_corps_inattendu_ne_fait_pas_echouer_la_journalisation(self, caplog):
        from ai.providers.anthropic import _log_status_error

        with caplog.at_level(logging.INFO):
            _log_status_error(StatusError(500, {"pas": "la forme attendue"}))

        assert "500" in caplog.text


class TestResponseReading:
    def test_une_reponse_sans_texte_est_inexploitable(self):
        message = type("M", (), {"content": []})()

        with pytest.raises(AIResponseUnusable):
            AnthropicProvider._read(message)

    def test_une_reponse_qui_n_est_pas_du_json_est_inexploitable(self):
        bloc = type("B", (), {"type": "text", "text": "je ne suis pas du JSON"})()
        message = type("M", (), {"content": [bloc]})()

        with pytest.raises(AIResponseUnusable, match="JSON"):
            AnthropicProvider._read(message)

    def test_une_reponse_qui_n_est_pas_un_objet_est_inexploitable(self):
        bloc = type("B", (), {"type": "text", "text": "[1, 2, 3]"})()
        message = type("M", (), {"content": [bloc]})()

        with pytest.raises(AIResponseUnusable, match="objet"):
            AnthropicProvider._read(message)

    def test_le_refus_ne_recopie_pas_la_reponse(self):
        bloc = type("B", (), {"type": "text", "text": "mon plat très personnel"})()
        message = type("M", (), {"content": [bloc]})()

        with pytest.raises(AIResponseUnusable) as leve:
            AnthropicProvider._read(message)

        assert "personnel" not in str(leve.value)


class TestTruncatedResponse:
    """Une réponse coupée par le budget doit se dire comme telle.

    Les jetons de réflexion s'imputent sur `max_tokens` : un budget trop serré
    coupe la réponse en plein JSON, et le parsing échoue alors sans expliquer
    pourquoi.
    """

    def test_une_reponse_coupee_est_annoncee(self):
        bloc = type("B", (), {"type": "text", "text": '{"days": [{"date"'})()
        message = type("M", (), {"content": [bloc], "stop_reason": "max_tokens"})()

        with pytest.raises(AIResponseUnusable, match="coupée"):
            AnthropicProvider._read(message)

    def test_une_reponse_complete_est_lue(self):
        bloc = type("B", (), {"type": "text", "text": '{"ok": true}'})()
        message = type("M", (), {"content": [bloc], "stop_reason": "end_turn"})()

        assert AnthropicProvider._read(message) == {"ok": True}
