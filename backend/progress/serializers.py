"""Serializers du suivi de progression."""

from decimal import Decimal

from rest_framework import serializers

from progress.models import MEASUREMENT_FIELDS, BodyMeasurementEntry, WeightEntry


class WeightEntrySerializer(serializers.ModelSerializer):
    """Pesée. L'utilisateur est toujours celui de la requête, jamais du payload."""

    class Meta:
        model = WeightEntry
        fields = ("id", "date", "weight_kg", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_weight_kg(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le poids doit être strictement positif.")
        return value


#: Plus petite mesure représentable au dixième : une mesure est nulle ou
#: strictement positive, jamais zéro (contrainte reprise de la base).
SMALLEST_MEASURE = Decimal("0.1")


class BodyMeasurementEntrySerializer(serializers.ModelSerializer):
    """Mensurations d'une date. Toutes les mesures sont facultatives."""

    class Meta:
        model = BodyMeasurementEntry
        fields = ("id", "date", *MEASUREMENT_FIELDS, "notes", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            **{field: {"min_value": SMALLEST_MEASURE} for field in MEASUREMENT_FIELDS},
            "body_fat_percent": {"min_value": SMALLEST_MEASURE, "max_value": Decimal(100)},
        }

    def validate(self, attrs):
        """Refuse une entrée qui ne porterait aucune mesure.

        Sur mise à jour partielle, la vérification porte sur le résultat
        fusionné : vider les six champs reviendrait à conserver une ligne
        sans contenu.
        """
        merged = {field: getattr(self.instance, field, None) for field in MEASUREMENT_FIELDS}
        merged.update({key: value for key, value in attrs.items() if key in MEASUREMENT_FIELDS})

        if all(value is None for value in merged.values()):
            raise serializers.ValidationError("Renseignez au moins une mesure.")

        return attrs


class ChartPointSerializer(serializers.Serializer):
    """Une mesure relevée et la moyenne mobile qu'elle clôt."""

    date = serializers.DateField()
    value = serializers.DecimalField(max_digits=8, decimal_places=2)
    moving_average = serializers.DecimalField(max_digits=8, decimal_places=2)


class ChartSeriesSerializer(serializers.Serializer):
    """Série d'une métrique sur une période (spec 04 §14)."""

    metric = serializers.CharField()
    unit = serializers.CharField()
    points = ChartPointSerializer(many=True)
    target = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    trend_per_week = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # `from` est un mot-clé Python : les deux bornes ne peuvent pas être
        # déclarées comme champs et sont ajoutées ici, pour que la réponse
        # emploie les mêmes noms que les paramètres de requête.
        data["from"] = instance["from"].isoformat()
        data["to"] = instance["to"].isoformat()
        return data
