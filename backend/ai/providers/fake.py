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


class FakeProvider:
    """Renvoie toujours la même analyse."""

    name = "fake"

    def structured_completion(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        images: tuple[ImagePart, ...] = (),
    ) -> dict:
        return {"items": [dict(detection) for detection in DETECTIONS]}
