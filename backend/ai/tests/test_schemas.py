"""Validation des sorties d'IA (spec 07 §4).

Le premier test de ce fichier est celui qui protège la règle la plus
fondamentale du projet : **une valeur nutritionnelle proposée par le modèle ne
doit jamais franchir la validation** (CLAUDE.md §2, spec 07 §1).
"""

from decimal import Decimal

import pytest

from ai.providers import AIResponseUnusable
from ai.schemas import (
    MEAL_SCAN_JSON_SCHEMA,
    UNSUPPORTED_SCHEMA_KEYWORDS,
    MealScanResultSerializer,
    validate_ai_output,
)


def keywords(node: object) -> set[str]:
    """Tous les mots-clés employés par un schéma, à toute profondeur."""
    if isinstance(node, dict):
        return set(node) | {key for value in node.values() for key in keywords(value)}
    if isinstance(node, list):
        return {key for item in node for key in keywords(item)}
    return set()


def detection(**overrides) -> dict:
    base = {
        "label": "poulet",
        "estimated_quantity": 150,
        "unit": "g",
        "confidence": 0.8,
        "alternatives": [],
    }
    return {**base, **overrides}


def validate(payload):
    return validate_ai_output(MealScanResultSerializer, payload)


class TestNutritionNeverPasses:
    """Le modèle propose des mots, jamais des calories."""

    def test_les_valeurs_nutritionnelles_sont_ecartees(self):
        result = validate(
            {
                "items": [
                    detection(
                        energy_kcal=9999,
                        protein_g=42,
                        carbohydrates_g=13,
                        fat_g=7,
                        calories=9999,
                    )
                ]
            }
        )

        item = result["items"][0]
        assert set(item) == {
            "label",
            "estimated_quantity",
            "unit",
            "confidence",
            "alternatives",
        }
        assert "energy_kcal" not in item
        assert "9999" not in str(item)

    def test_le_schema_n_emploie_aucun_mot_cle_refuse(self):
        """Les sorties structurées rejettent les bornes numériques et de taille.

        Un schéma qui en contient fait échouer **toute** la requête en 400, sans
        que rien ne distingue cette panne d'une autre côté utilisateur. Les
        bornes vivent donc dans le serializer, qui les applique de toute façon.
        """
        assert not keywords(MEAL_SCAN_JSON_SCHEMA) & UNSUPPORTED_SCHEMA_KEYWORDS

    def test_le_schema_envoye_interdit_tout_champ_supplementaire(self):
        item_schema = MEAL_SCAN_JSON_SCHEMA["properties"]["items"]["items"]

        assert item_schema["additionalProperties"] is False
        assert MEAL_SCAN_JSON_SCHEMA["additionalProperties"] is False
        # Aucune propriété nutritionnelle n'est même proposée au modèle.
        assert set(item_schema["properties"]) == {
            "label",
            "estimated_quantity",
            "unit",
            "confidence",
            "alternatives",
        }


class TestValidation:
    def test_une_reponse_correcte_est_validee(self):
        result = validate({"items": [detection()]})

        item = result["items"][0]
        assert item["label"] == "poulet"
        assert item["estimated_quantity"] == Decimal("150")
        assert item["unit"] == "g"

    def test_une_liste_vide_est_acceptee(self):
        """Une photo sans aliment n'est pas une erreur (spec 07 §5)."""
        assert validate({"items": []})["items"] == []

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param("pas un objet", id="reponse-non-objet"),
            pytest.param({}, id="items-manquant"),
            pytest.param({"items": "poulet"}, id="items-non-liste"),
            pytest.param({"items": [{"label": "poulet"}]}, id="champs-manquants"),
            pytest.param({"items": [detection(label="")]}, id="libelle-vide"),
            pytest.param({"items": [detection(confidence=5)]}, id="confiance-hors-bornes"),
            pytest.param({"items": [detection(confidence=-1)]}, id="confiance-negative"),
            pytest.param({"items": [detection(estimated_quantity=0)]}, id="quantite-nulle"),
            pytest.param({"items": [detection(estimated_quantity=-30)]}, id="quantite-negative"),
            pytest.param({"items": [detection(unit="cuillère")]}, id="unite-inconnue"),
            pytest.param(
                {"items": [detection(estimated_quantity="beaucoup")]}, id="quantite-texte"
            ),
        ],
    )
    def test_une_reponse_invalide_est_refusee(self, payload):
        with pytest.raises(AIResponseUnusable):
            validate(payload)

    def test_le_refus_ne_recopie_pas_la_reponse(self):
        """Le message de refus nomme les champs, pas ce qu'ils contenaient."""
        with pytest.raises(AIResponseUnusable) as raised:
            validate({"items": [detection(label="mon plat très personnel", confidence=12)]})

        assert "personnel" not in str(raised.value)

    def test_trop_d_aliments_est_refuse(self):
        with pytest.raises(AIResponseUnusable):
            validate({"items": [detection() for _ in range(50)]})
