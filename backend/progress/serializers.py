"""Serializers du suivi de progression."""

from rest_framework import serializers

from progress.models import WeightEntry


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
