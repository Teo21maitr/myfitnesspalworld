"""Meal Scan : de la photo aux suggestions (spec 07 §5).

Ce module tient la règle qui donne son sens à toute l'étape :

> **Le modèle propose des mots, la base fournit les calories.**

Ce qui revient du fournisseur, ce sont des libellés et des quantités visibles.
Chaque libellé est cherché dans le référentiel avec la recherche ordinaire —
celle du champ de recherche, pas une variante — et les valeurs nutritionnelles
affichées sont celles des fiches trouvées.

Rien n'est écrit dans le journal ici : une suggestion attend une confirmation
(CLAUDE.md §2).
"""

from decimal import Decimal

from ai.serializers import FoodCandidateSerializer
from nutrition.services.quantities import available_units
from nutrition.services.search import search_foods

#: Assez de choix pour corriger une erreur d'identification, assez peu pour
#: rester lisible sur un téléphone.
CANDIDATES_PER_ITEM = 5


def _candidates(user, label: str) -> list:
    """Aliments correspondant au libellé, du plus pertinent au moins."""
    queryset = search_foods(user, label).prefetch_related("portions")
    return list(queryset[:CANDIDATES_PER_ITEM])


def _usable_unit(food, unit: str) -> str:
    """Unité proposable pour cet aliment.

    Une unité que le backend refuserait ferait échouer la confirmation en 400,
    et l'utilisateur verrait une erreur pour une phrase qu'il n'a pas écrite.
    On retombe alors sur l'unité de référence de l'aliment (spec 01 §9).
    """
    return unit if unit in available_units(food) else food.reference_unit


def build_suggestions(user, items: list[dict]) -> list[dict]:
    """Transforme les détections du modèle en suggestions exploitables."""
    suggestions = []

    for item in items:
        candidates = _candidates(user, item["label"])
        quantity: Decimal = item["estimated_quantity"]
        unit = item["unit"]

        # L'unité est ajustée sur le candidat retenu par défaut. Changer de
        # candidat dans l'écran de correction relance le même arbitrage côté
        # frontend, à partir de `available_units`.
        if candidates:
            unit = _usable_unit(candidates[0], unit)

        suggestions.append(
            {
                "label": item["label"],
                "estimated_quantity": str(quantity),
                "unit": unit,
                "confidence": item["confidence"],
                "alternatives": item.get("alternatives", []),
                # Liste vide plutôt qu'erreur : l'interface bascule alors sur
                # la recherche manuelle (spec 07 §5).
                "candidates": FoodCandidateSerializer(candidates, many=True).data,
            }
        )

    return suggestions
