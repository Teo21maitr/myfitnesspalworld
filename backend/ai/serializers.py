"""Serializers de l'app `ai`.

Une suggestion n'est jamais qu'une proposition : elle ne s'écrit nulle part
tant que l'utilisateur ne l'a pas confirmée par `/diary/entries/` (spec 07 §5).
"""

from rest_framework import serializers

from nutrition.models import Food
from nutrition.services.quantities import available_units as food_available_units

#: Ce qu'il faut pour choisir en connaissance de cause, sans ouvrir la fiche.
CANDIDATE_NUTRIENTS = ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")


class FoodCandidateSerializer(serializers.ModelSerializer):
    """Aliment de la base proposé pour un libellé détecté.

    Volontairement autonome : la tâche s'exécute dans un worker, sans requête
    HTTP dont un serializer pourrait tirer l'utilisateur courant.

    `available_units` est inclus pour que l'écran de correction propose une
    unité que le backend acceptera, sans avoir à recharger chaque fiche
    (spec 01 §9).
    """

    source_label = serializers.CharField(source="get_source_display", read_only=True)
    nutrition = serializers.SerializerMethodField()
    available_units = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = (
            "id",
            "name",
            "brand",
            "source",
            "source_label",
            "reference_amount",
            "reference_unit",
            "nutrition",
            "available_units",
        )

    def get_nutrition(self, obj: Food) -> dict:
        nutrition = getattr(obj, "nutrition", None)
        values = {}

        for name in CANDIDATE_NUTRIENTS:
            value = getattr(nutrition, name, None) if nutrition else None
            # Chaîne plutôt que Decimal, comme partout ailleurs dans l'API : ce
            # résultat est stocké en JSON dans la tâche, et un Decimal n'y
            # entre pas. Une valeur inconnue reste nulle, jamais zéro
            # (spec 01 §8).
            values[name] = str(value) if value is not None else None

        return values

    def get_available_units(self, obj: Food) -> list[str]:
        return food_available_units(obj)
