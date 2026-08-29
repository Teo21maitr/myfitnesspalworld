"""Sérialisation de l'analyse et des rapports (spec 04 §17-18).

Deux champs comptent plus que les chiffres eux-mêmes : `logged_days`, qui dit
sur combien de journées porte une moyenne, et `is_partial`, qui dit qu'un total
additionne ce qu'on sait sans prétendre à l'exhaustivité. Les taire rendrait les
valeurs plausibles et invérifiables.
"""

from rest_framework import serializers

from nutrition.models.nutrients import nutrient_label


class SourceSerializer(serializers.Serializer):
    """Un aliment et sa contribution à un nutriment."""

    name = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    entries = serializers.IntegerField()
    #: Part du total **connu**. Un minorant quand l'analyse est partielle.
    share = serializers.FloatField()


class NutrientAnalysisSerializer(serializers.Serializer):
    """`GET /analysis/food/` (spec 04 §18)."""

    nutrient = serializers.CharField()
    label = serializers.SerializerMethodField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    sources = SourceSerializer(many=True)
    unknown_entries = serializers.IntegerField()
    logged_days = serializers.IntegerField()
    is_partial = serializers.BooleanField()

    def get_label(self, instance) -> str:
        return nutrient_label(instance.nutrient)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # `from` est un mot-clé Python : les bornes portent les mêmes noms que
        # les paramètres de requête, mais ne peuvent pas être des champs.
        data["from"] = instance.start.isoformat()
        data["to"] = instance.end.isoformat()
        return data


class ReportDaySerializer(serializers.Serializer):
    """Une journée tenue du rapport."""

    date = serializers.DateField()
    entries = serializers.IntegerField()
    target_calories = serializers.DecimalField(max_digits=9, decimal_places=2, allow_null=True)
    weight_kg = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    totals = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    )
    incomplete_nutrients = serializers.ListField(child=serializers.CharField())


class ReportSerializer(serializers.Serializer):
    """`GET /reports/summary/` et `GET /analysis/weekly/` (spec 04 §17-18).

    Le même sérialiseur sert les deux : un résumé hebdomadaire est un rapport
    sur sept jours, et en produire deux versions les ferait diverger.
    """

    days = ReportDaySerializer(many=True)
    averages = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    )
    adherence = serializers.DictField(child=serializers.IntegerField())
    top_foods = SourceSerializer(many=True)
    logged_days = serializers.IntegerField()
    calendar_days = serializers.IntegerField()
    weight_change = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["from"] = instance.start.isoformat()
        data["to"] = instance.end.isoformat()
        data["weight"] = {
            "points": [
                {
                    "date": point["date"].isoformat(),
                    "value": str(point["value"]),
                    "moving_average": str(point["moving_average"]),
                }
                for point in instance.weight.get("points") or []
            ],
            "target": str(instance.weight["target"]) if instance.weight.get("target") else None,
            "trend_per_week": (
                str(instance.weight["trend_per_week"])
                if instance.weight.get("trend_per_week") is not None
                else None
            ),
        }
        return data
