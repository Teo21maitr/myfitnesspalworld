"""Fournisseur simulé, pour le développement sans clé et les parcours de test.

Il rend le pipeline complet exécutable — endpoint, tâche Celery, validation,
résolution des aliments — sans appel facturé et sans réponse variable d'une
exécution à l'autre.

Il est **interdit en production** (`config/settings/production.py`) : une
suggestion inventée y serait servie sans le moindre signe extérieur.
"""

from .base import ImagePart

#: Deux aliments présents dans l'extrait Ciqual versionné, pour que la
#: résolution trouve de la matière dans une base de développement.
DETECTIONS = [
    {
        "label": "poulet",
        "estimated_quantity": 150,
        "unit": "g",
        "confidence": 0.82,
        "alternatives": ["cuisse de poulet"],
        # Volontairement présent, et volontairement faux. Un vrai modèle
        # proposera tôt ou tard une valeur nutritionnelle sans qu'on la lui
        # demande ; ce champ garantit qu'aucune exécution — test unitaire ou
        # parcours complet — ne passe sans prouver qu'elle n'entre nulle part.
        "energy_kcal": 9999,
    },
    {
        "label": "abricot",
        "estimated_quantity": 80,
        "unit": "g",
        "confidence": 0.55,
        "alternatives": [],
    },
]


#: Étiquette simulée. `fiber_g` est nul **volontairement** : chaque exécution
#: prouve ainsi qu'une valeur non lue reste nulle et ne devient pas zéro.
LABEL = {
    "name": "Produit de démonstration",
    "brand": "Marque simulée",
    "barcode": "7310865691750",
    "basis": "100g",
    "nutrition": {
        "energy_kcal": 250,
        "protein_g": 8.5,
        "carbohydrates_g": 30,
        "sugars_g": 4.2,
        "fat_g": 10,
        "fiber_g": None,
        "salt_g": 0.9,
        "sodium_mg": None,
    },
}


class FakeProvider:
    """Renvoie une réponse fixe, choisie d'après le schéma demandé."""

    name = "fake"

    def structured_completion(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        images: tuple[ImagePart, ...] = (),
        max_tokens: int | None = None,
        effort: str | None = None,
    ) -> dict:
        # Le schéma dit quelle tâche est en cours : un fournisseur simulé qui
        # répondrait toujours la même chose ferait échouer les autres.
        properties = schema.get("properties", {})
        if "nutrition" in properties:
            return {**LABEL, "nutrition": dict(LABEL["nutrition"])}
        if "days" in properties:
            return _fake_plan(schema)
        return {"items": [dict(detection) for detection in DETECTIONS]}


#: Aliments proposés par le plan simulé. Présents dans l'extrait Ciqual
#: versionné, pour que la résolution trouve de la matière.
PLAN_LABELS = ("poulet", "abricot")


def _fake_plan(schema: dict) -> dict:
    """Plan simulé, calqué sur les dates et les repas réellement demandés.

    Les énumérations du schéma portent l'information : les relire évite de
    devoir la passer au fournisseur par un autre chemin, et garantit que la
    réponse simulée est toujours cohérente avec la demande.
    """
    day_schema = schema["properties"]["days"]["items"]["properties"]
    dates = day_schema["date"]["enum"]
    meals = day_schema["meals"]["items"]["properties"]["meal"]["enum"]

    return {
        "days": [
            {
                "date": date,
                "meals": [
                    {
                        "meal": meal,
                        "items": [
                            {
                                "type": "food",
                                "label": PLAN_LABELS[index % len(PLAN_LABELS)],
                                "quantity": 150,
                                "unit": "g",
                            }
                        ],
                    }
                    for index, meal in enumerate(meals)
                ],
            }
            for date in dates
        ],
        "recipes": [],
    }
