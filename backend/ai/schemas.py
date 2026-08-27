"""Schémas des sorties d'IA et leur validation (spec 07 §4).

Deux barrières, volontairement redondantes :

1. le **schéma JSON** envoyé au fournisseur, qui contraint sa réponse ;
2. le **serializer**, qui valide ce qui revient réellement.

La seconde ne fait pas double emploi avec la première. Un fournisseur peut
ignorer le schéma, en changer l'interprétation d'une version à l'autre, ou être
remplacé par un autre dont la mécanique diffère. Surtout, un schéma respecté ne
garantit pas une valeur sensée : une confiance de 5 ou une quantité négative
sont conformes au type et absurdes.

**Aucun des deux ne comporte de champ nutritionnel.** C'est la règle
fondamentale du projet (CLAUDE.md §2, spec 07 §1) : le modèle propose des mots
et des quantités ; les calories viennent de la base. Un serializer ne conserve
que les champs qu'il déclare — tout le reste est écarté à la validation, et il
n'y a donc rien à laisser fuir vers le journal.
"""

from decimal import Decimal

from rest_framework import serializers

from .providers import AIResponseUnusable

#: Unités qu'un modèle peut proposer en regardant une assiette. Ce sont les
#: trois unités de référence du projet : ni « kg » ni « cuillère » n'ont de
#: sens pour une estimation visuelle.
DETECTABLE_UNITS = ("g", "ml", "unité")

#: Une photo d'assiette ne contient pas cinquante aliments. Cette borne protège
#: la résolution en base d'une réponse emballée.
MAX_DETECTED_ITEMS = 20

MAX_ALTERNATIVES = 5

#: Schéma transmis au fournisseur. `additionalProperties: false` est la
#: première barrière contre un champ nutritionnel spontané.
MEAL_SCAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "maxItems": MAX_DETECTED_ITEMS,
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Nom de l'aliment en français, au singulier.",
                    },
                    "estimated_quantity": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Quantité visible estimée.",
                    },
                    "unit": {"type": "string", "enum": list(DETECTABLE_UNITS)},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "alternatives": {
                        "type": "array",
                        "maxItems": MAX_ALTERNATIVES,
                        "items": {"type": "string"},
                        "description": "Autres identifications plausibles.",
                    },
                },
                "required": ["label", "estimated_quantity", "unit", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


class MealScanItemSerializer(serializers.Serializer):
    """Un aliment détecté sur la photo (spec 07 §5)."""

    label = serializers.CharField(max_length=200)
    estimated_quantity = serializers.DecimalField(
        max_digits=9, decimal_places=3, min_value=Decimal("0.001")
    )
    unit = serializers.ChoiceField(choices=DETECTABLE_UNITS)
    confidence = serializers.FloatField(min_value=0, max_value=1)
    alternatives = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        default=list,
        max_length=MAX_ALTERNATIVES,
    )


class MealScanResultSerializer(serializers.Serializer):
    items = MealScanItemSerializer(many=True, allow_empty=True)

    def validate_items(self, value: list) -> list:
        if len(value) > MAX_DETECTED_ITEMS:
            raise serializers.ValidationError("Trop d'aliments détectés.")
        return value


def validate_ai_output(serializer_class, payload: object) -> dict:
    """Valide une sortie d'IA, ou refuse la réponse.

    Traduit l'échec en `AIResponseUnusable` : une réponse inexploitable est un
    fait de la frontière IA, pas une erreur de saisie de l'utilisateur, et ne
    doit pas remonter sous la forme d'une `ValidationError` DRF.
    """
    if not isinstance(payload, dict):
        raise AIResponseUnusable("Réponse d'IA inattendue.")

    serializer = serializer_class(data=payload)
    if not serializer.is_valid():
        # Les clés en défaut suffisent au diagnostic ; les valeurs reçues
        # décrivent le repas de quelqu'un et ne sont pas journalisées.
        raise AIResponseUnusable("Réponse d'IA invalide : " + ", ".join(sorted(serializer.errors)))
    return serializer.validated_data
