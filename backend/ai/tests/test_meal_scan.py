"""Résolution des détections en suggestions (spec 07 §5)."""

from decimal import Decimal

import pytest

from ai.services.meal_scan import CANDIDATES_PER_ITEM, build_suggestions
from nutrition.models import Food, FoodNutrition, FoodSource, FoodVisibility

pytestmark = pytest.mark.django_db


def detection(**overrides) -> dict:
    base = {
        "label": "poulet",
        "estimated_quantity": Decimal("150"),
        "unit": "g",
        "confidence": 0.8,
        "alternatives": [],
    }
    return {**base, **overrides}


class TestCaloriesComeFromTheDatabase:
    """Le cœur de l'étape : la base fournit les valeurs, jamais le modèle."""

    def test_les_candidats_portent_la_nutrition_de_la_fiche(self, active_user, chicken):
        suggestions = build_suggestions(active_user, [detection()])

        candidate = suggestions[0]["candidates"][0]
        assert candidate["id"] == chicken.pk
        assert Decimal(candidate["nutrition"]["energy_kcal"]) == Decimal("120")

    def test_aucune_valeur_du_modele_ne_traverse(self, active_user, chicken):
        """Même en forçant un champ nutritionnel, il n'atteint pas la sortie."""
        suggestions = build_suggestions(active_user, [detection(energy_kcal=9999)])

        assert "9999" not in str(suggestions)

    def test_un_nutriment_inconnu_reste_nul(self, active_user, apricot):
        suggestions = build_suggestions(active_user, [detection(label="abricot")])

        nutrition = suggestions[0]["candidates"][0]["nutrition"]
        assert Decimal(nutrition["energy_kcal"]) == Decimal("48")
        # Jamais zéro pour une valeur non renseignée (spec 01 §8).
        assert nutrition["protein_g"] is None


class TestSuggestions:
    def test_le_libelle_et_la_quantite_du_modele_sont_conserves(self, active_user, chicken):
        suggestions = build_suggestions(active_user, [detection(estimated_quantity=Decimal("175"))])

        assert suggestions[0]["label"] == "poulet"
        assert Decimal(suggestions[0]["estimated_quantity"]) == Decimal("175")
        assert suggestions[0]["confidence"] == 0.8

    def test_un_libelle_sans_correspondance_donne_une_liste_vide(self, active_user, chicken):
        """Pas une erreur : l'interface bascule sur la recherche manuelle."""
        suggestions = build_suggestions(active_user, [detection(label="zorglub")])

        assert suggestions[0]["candidates"] == []
        assert suggestions[0]["label"] == "zorglub"

    def test_le_nombre_de_candidats_est_borne(self, active_user):
        for index in range(CANDIDATES_PER_ITEM + 3):
            food = Food.objects.create(
                source=FoodSource.CIQUAL, external_id=f"c{index}", name=f"Poulet {index}"
            )
            FoodNutrition.objects.create(food=food, energy_kcal=Decimal("100"))

        suggestions = build_suggestions(active_user, [detection()])

        assert len(suggestions[0]["candidates"]) == CANDIDATES_PER_ITEM

    def test_l_aliment_prive_d_un_autre_n_est_pas_propose(self, active_user, other_user):
        private = Food.objects.create(
            source=FoodSource.USER,
            owner=other_user,
            name="Poulet secret",
            visibility=FoodVisibility.PRIVATE,
        )
        FoodNutrition.objects.create(food=private, energy_kcal=Decimal("100"))

        suggestions = build_suggestions(active_user, [detection()])

        assert all(candidate["id"] != private.pk for candidate in suggestions[0]["candidates"])

    def test_chaque_detection_donne_une_suggestion(self, active_user, chicken, apricot):
        suggestions = build_suggestions(
            active_user, [detection(), detection(label="abricot", estimated_quantity=Decimal("80"))]
        )

        assert [item["label"] for item in suggestions] == ["poulet", "abricot"]


class TestUnits:
    def test_une_unite_calculable_est_conservee(self, active_user, chicken):
        suggestions = build_suggestions(active_user, [detection(unit="g")])

        assert suggestions[0]["unit"] == "g"

    def test_une_unite_incalculable_retombe_sur_l_unite_de_reference(self, active_user, milk):
        """Des grammes sur un aliment en millilitres : `/diary/entries/` les
        refuserait en 400 (spec 01 §9)."""
        suggestions = build_suggestions(active_user, [detection(label="lait", unit="g")])

        assert suggestions[0]["candidates"][0]["id"] == milk.pk
        assert suggestions[0]["unit"] == "ml"

    def test_les_unites_disponibles_accompagnent_chaque_candidat(self, active_user, milk):
        suggestions = build_suggestions(active_user, [detection(label="lait", unit="ml")])

        units = suggestions[0]["candidates"][0]["available_units"]
        assert "ml" in units
        assert "verre" in units
        assert "g" not in units

    def test_sans_candidat_l_unite_du_modele_est_conservee(self, active_user):
        suggestions = build_suggestions(active_user, [detection(label="zorglub", unit="unité")])

        assert suggestions[0]["unit"] == "unité"
