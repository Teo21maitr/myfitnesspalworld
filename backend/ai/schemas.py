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

#: Mots-clés que les sorties structurées **n'acceptent pas**.
#:
#: Vérifié contre l'API : `maxItems`, `exclusiveMinimum`, `minimum` et
#: `maximum` font échouer la requête en 400. Le schéma envoyé contraint donc la
#: *forme* — quels champs, de quels types, et rien d'autre — tandis que les
#: *valeurs* sont bornées par le serializer plus bas.
#:
#: Cette répartition n'est pas un pis-aller : une confiance de 5 ou une
#: quantité négative auraient de toute façon demandé une validation métier,
#: puisqu'elles sont conformes au type. C'est la raison d'être de la seconde
#: barrière.
UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {"maxItems", "minItems", "exclusiveMinimum", "exclusiveMaximum", "minimum", "maximum"}
)

#: Schéma transmis au fournisseur. `additionalProperties: false` est la
#: première barrière contre un champ nutritionnel spontané.
MEAL_SCAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Nom de l'aliment en français, au singulier.",
                    },
                    "estimated_quantity": {
                        "type": "number",
                        "description": "Quantité visible estimée, strictement positive.",
                    },
                    "unit": {"type": "string", "enum": list(DETECTABLE_UNITS)},
                    "confidence": {
                        "type": "number",
                        "description": "Confiance entre 0 et 1.",
                    },
                    "alternatives": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            f"Autres identifications plausibles, {MAX_ALTERNATIVES} au maximum."
                        ),
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


# -----------------------------------------------------------------------------
# Lecture d'étiquette nutritionnelle
# -----------------------------------------------------------------------------

#: Nutriments qu'une étiquette européenne déclare et que le modèle de données
#: sait porter. Les acides gras saturés, pourtant obligatoires sur l'étiquette,
#: n'ont pas de colonne : la spec 01 §4 ne les prévoit pas, et on ne les invente
#: pas ici.
LABEL_NUTRIENTS = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "sugars_g",
    "fat_g",
    "fiber_g",
    "salt_g",
    "sodium_mg",
)

#: Base de déclaration lue sur l'étiquette. `unknown` couvre le cas où seule
#: une colonne « par portion » figure : mieux vaut ne rien rendre que des
#: valeurs fausses d'un facteur trois.
LABEL_BASES = ("100g", "100ml", "unknown")

#: Un nombre, ou rien. **Rien n'est pas zéro** : zéro affirme que le produit
#: n'en contient pas, ce que seule une étiquette lisible permet de dire.
_NULLABLE_NUMBER = {"type": ["number", "null"]}
_NULLABLE_STRING = {"type": ["string", "null"]}

LABEL_SCAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Nom du produit tel qu'écrit sur l'emballage."},
        "brand": {**_NULLABLE_STRING, "description": "Marque, si elle figure."},
        "barcode": {**_NULLABLE_STRING, "description": "Code-barres, uniquement s'il est lisible."},
        "basis": {
            "type": "string",
            "enum": list(LABEL_BASES),
            "description": "Colonne lue : pour 100 g, pour 100 ml, ou aucune des deux.",
        },
        "nutrition": {
            "type": "object",
            "properties": {name: dict(_NULLABLE_NUMBER) for name in LABEL_NUTRIENTS},
            "required": list(LABEL_NUTRIENTS),
            "additionalProperties": False,
        },
    },
    "required": ["name", "brand", "barcode", "basis", "nutrition"],
    "additionalProperties": False,
}


class LabelNutritionSerializer(serializers.Serializer):
    """Valeurs lues sur l'étiquette, toutes facultatives et toutes nullables."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in LABEL_NUTRIENTS:
            self.fields[name] = serializers.DecimalField(
                max_digits=12,
                decimal_places=3,
                min_value=Decimal("0"),
                allow_null=True,
                required=False,
                default=None,
            )


class LabelScanResultSerializer(serializers.Serializer):
    """Brouillon d'aliment lu sur une étiquette (spec 01 §11)."""

    name = serializers.CharField(max_length=255)
    brand = serializers.CharField(max_length=255, allow_null=True, allow_blank=True, required=False)
    barcode = serializers.CharField(
        max_length=64, allow_null=True, allow_blank=True, required=False
    )
    basis = serializers.ChoiceField(choices=LABEL_BASES)
    nutrition = LabelNutritionSerializer()
