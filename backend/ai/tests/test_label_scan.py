"""Lecture d'étiquette : du brouillon à ce qu'il ne doit jamais contenir.

Le premier bloc protège la règle de l'étape : **non lu n'est pas zéro**. Un
zéro enregistré affirme que le produit ne contient pas ce nutriment, et ce
mensonge serait recopié dans chaque snapshot de journal qui suivra
(spec 01 §8).
"""

from decimal import Decimal

import pytest

from ai.schemas import LABEL_NUTRIENTS, LabelScanResultSerializer, validate_ai_output
from ai.services.label_scan import build_draft

pytestmark = pytest.mark.django_db


def reading(**overrides) -> dict:
    base = {
        "name": "Knäckebröd",
        "brand": "Wasa",
        "barcode": "7300400481106",
        "basis": "100g",
        "nutrition": dict.fromkeys(LABEL_NUTRIENTS, 1),
    }
    nutrition = {**base["nutrition"], **overrides.pop("nutrition", {})}
    return {**base, **overrides, "nutrition": nutrition}


def draft_of(**overrides) -> dict:
    validated = validate_ai_output(LabelScanResultSerializer, reading(**overrides))
    return build_draft(validated)


class TestUnreadIsNotZero:
    def test_une_valeur_non_lue_reste_nulle(self):
        result = draft_of(nutrition={"fiber_g": None})

        assert result["draft"]["nutrition"]["fiber_g"] is None
        assert "fiber_g" in result["unreadable"]

    def test_un_vrai_zero_est_conservé(self):
        """Un produit sans sucre déclare bien « 0 g » : ce n'est pas une lacune."""
        result = draft_of(nutrition={"sugars_g": 0})

        assert Decimal(result["draft"]["nutrition"]["sugars_g"]) == Decimal("0")
        assert "sugars_g" not in result["unreadable"]

    def test_ce_qui_manque_est_nommé(self):
        result = draft_of(nutrition={"fiber_g": None, "sodium_mg": None})

        assert set(result["unreadable"]) == {"fiber_g", "sodium_mg"}

    def test_une_etiquette_entierement_lue_ne_laisse_rien_de_manquant(self):
        assert draft_of()["unreadable"] == []


class TestDeclarationBasis:
    def test_pour_100_g_donne_une_reference_en_grammes(self):
        result = draft_of(basis="100g")

        assert result["draft"]["reference_unit"] == "g"
        assert result["draft"]["reference_amount"] == "100"

    def test_pour_100_ml_donne_une_reference_en_millilitres(self):
        assert draft_of(basis="100ml")["draft"]["reference_unit"] == "ml"

    def test_sans_colonne_pour_100_aucune_valeur_n_est_reprise(self):
        """Une colonne « par portion » recopiée fausserait tout d'un facteur trois."""
        result = draft_of(basis="unknown")

        assert all(value is None for value in result["draft"]["nutrition"].values())
        assert set(result["unreadable"]) == set(LABEL_NUTRIENTS)

    def test_l_identite_du_produit_survit_a_une_base_inconnue(self):
        result = draft_of(basis="unknown")

        assert result["draft"]["name"] == "Knäckebröd"
        assert result["draft"]["brand"] == "Wasa"


class TestBarcode:
    def test_un_code_valide_est_conservé(self):
        assert draft_of()["draft"]["barcode"] == "7300400481106"

    def test_les_separateurs_sont_retirés(self):
        assert draft_of(barcode="7 300400 481106")["draft"]["barcode"] == "7300400481106"

    @pytest.mark.parametrize(
        "lu",
        [
            pytest.param("123", id="trop-court"),
            pytest.param("ABCDEFGH", id="pas-des-chiffres"),
            pytest.param("", id="vide"),
            pytest.param(None, id="absent"),
        ],
    )
    def test_un_code_douteux_vaut_mieux_absent(self, lu):
        """Un code mal lu ferait créer un doublon sous une identité fausse."""
        assert draft_of(barcode=lu)["draft"]["barcode"] == ""


class TestValidation:
    def test_une_valeur_negative_est_refusee(self):
        from ai.providers import AIResponseUnusable

        with pytest.raises(AIResponseUnusable):
            validate_ai_output(LabelScanResultSerializer, reading(nutrition={"energy_kcal": -10}))

    def test_une_base_inconnue_du_schema_est_refusee(self):
        from ai.providers import AIResponseUnusable

        with pytest.raises(AIResponseUnusable):
            validate_ai_output(LabelScanResultSerializer, reading(basis="par-portion"))

    def test_un_nom_manquant_est_refuse(self):
        from ai.providers import AIResponseUnusable

        payload = reading()
        del payload["name"]

        with pytest.raises(AIResponseUnusable):
            validate_ai_output(LabelScanResultSerializer, payload)

    def test_le_schema_n_emploie_aucun_mot_cle_refuse(self):
        """Même contrainte que pour le scan de repas, vérifiée contre l'API."""
        from ai.schemas import LABEL_SCAN_JSON_SCHEMA, UNSUPPORTED_SCHEMA_KEYWORDS

        from .test_schemas import keywords

        assert not keywords(LABEL_SCAN_JSON_SCHEMA) & UNSUPPORTED_SCHEMA_KEYWORDS
