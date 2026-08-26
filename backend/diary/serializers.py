"""Serializers du journal (spec 04 §4 et §5)."""

from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from diary.models import SNAPSHOT_NUTRIENT_FIELDS, DiaryEntry, EntryType, MealType
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food
from nutrition.serializers import DailyValuesSerializer

#: Noms des nutriments, sans le préfixe de snapshot.
NUTRIENT_NAMES = [field.removeprefix("snapshot_") for field in SNAPSHOT_NUTRIENT_FIELDS]


def nutrition_fields() -> dict:
    """Champs décimaux d'un bloc nutritionnel, tous facultatifs.

    Des `DecimalField` et non des flottants : les valeurs nutritionnelles sont
    sérialisées en chaînes partout dans l'API (spec 10 §2).
    """
    return {
        name: serializers.DecimalField(
            max_digits=12, decimal_places=3, read_only=True, allow_null=True
        )
        for name in NUTRIENT_NAMES
    }


ComputedNutritionSerializer = type(
    "ComputedNutritionSerializer", (serializers.Serializer,), nutrition_fields()
)


class MealTypeSerializer(serializers.ModelSerializer):
    """Repas d'un utilisateur."""

    is_system = serializers.BooleanField(read_only=True)

    class Meta:
        model = MealType
        fields = ("id", "name", "slug", "sort_order", "is_active", "is_system", "system_key")
        read_only_fields = ("id", "slug", "is_system", "system_key")


class MealTypeReorderSerializer(serializers.Serializer):
    """Nouvel ordre des repas."""

    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class DiaryEntrySerializer(serializers.ModelSerializer):
    """Entrée de journal, avec ses valeurs réellement consommées.

    `computed` est calculé côté serveur : le frontend n'a jamais à refaire la
    multiplication pour l'affichage définitif.
    """

    computed = serializers.SerializerMethodField()
    meal_type_id = serializers.IntegerField(source="meal_type.id", read_only=True)

    class Meta:
        model = DiaryEntry
        fields = (
            "id",
            "meal_type_id",
            "entry_type",
            "consumed_at",
            "quantity",
            "unit_label",
            "note",
            "food",
            "snapshot_name",
            "snapshot_brand",
            "snapshot_source",
            "snapshot_reference_amount",
            "snapshot_reference_unit",
            "computed",
        )
        read_only_fields = fields

    def get_computed(self, entry: DiaryEntry) -> dict:
        return ComputedNutritionSerializer(entries_service.computed_nutrition(entry)).data


class DiaryEntryWriteSerializer(serializers.Serializer):
    """Création d'une entrée : aliment ou ajout rapide (spec 04 §4).

    L'aliment et le repas sont résolus sur l'utilisateur appelant : ni l'un ni
    l'autre n'est accepté du frontend comme source de vérité (spec 05 §12).
    """

    date = serializers.DateField()
    meal_type_id = serializers.IntegerField()
    entry_type = serializers.ChoiceField(
        choices=[EntryType.FOOD, EntryType.QUICK_ADD], default=EntryType.FOOD
    )
    consumed_at = serializers.DateTimeField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")

    # Aliment
    food_id = serializers.IntegerField(required=False)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, required=False)
    unit_label = serializers.CharField(required=False, max_length=40)

    # Ajout rapide
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    energy_kcal = serializers.DecimalField(
        max_digits=9, decimal_places=3, required=False, allow_null=True
    )
    protein_g = serializers.DecimalField(
        max_digits=9, decimal_places=3, required=False, allow_null=True
    )
    carbohydrates_g = serializers.DecimalField(
        max_digits=9, decimal_places=3, required=False, allow_null=True
    )
    fat_g = serializers.DecimalField(
        max_digits=9, decimal_places=3, required=False, allow_null=True
    )

    def validate_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return value

    def validate_meal_type_id(self, value: int) -> int:
        user = self.context["request"].user
        if not meal_types_for(user).filter(pk=value).exists():
            raise serializers.ValidationError("Ce repas n’existe pas.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["entry_type"] == EntryType.FOOD:
            missing = [
                field for field in ("food_id", "quantity", "unit_label") if attrs.get(field) is None
            ]
            if missing:
                raise serializers.ValidationError(
                    dict.fromkeys(missing, "Ce champ est obligatoire pour un aliment.")
                )
        elif attrs.get("energy_kcal") is None:
            raise serializers.ValidationError(
                {"energy_kcal": "Un ajout rapide demande au moins des calories."}
            )

        return attrs

    def resolve_food(self, food_id: int) -> Food:
        """Aliment visible par l'appelant, sinon 400.

        Le filtrage passe par `visible_to`, écrit à l'étape 4 : impossible de
        journaliser un aliment qu'on n'a pas le droit de consulter.
        """
        user = self.context["request"].user
        food = (
            Food.objects.visible_to(user)
            .select_related("nutrition")
            .prefetch_related("portions")
            .filter(pk=food_id)
            .first()
        )
        if food is None:
            raise serializers.ValidationError({"food_id": "Cet aliment est introuvable."})
        return food

    def resolve_consumed_at(self, attrs: dict) -> datetime:
        """Horodatage automatique à l'ajout, modifiable ensuite (spec 01 §5)."""
        provided = attrs.get("consumed_at")
        if provided is not None:
            return provided

        now = timezone.localtime()
        day = attrs["date"]
        # Sur une date passée ou future, l'heure courante reste le repère le
        # plus naturel ; seule la date change.
        return timezone.make_aware(datetime.combine(day, now.time().replace(microsecond=0)))


class DiaryEntryUpdateSerializer(serializers.Serializer):
    """Modification d'une entrée existante."""

    meal_type_id = serializers.IntegerField(required=False)
    consumed_at = serializers.DateTimeField(required=False)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, required=False)
    unit_label = serializers.CharField(required=False, max_length=40)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return value

    def validate_meal_type_id(self, value: int) -> int:
        user = self.context["request"].user
        if not meal_types_for(user).filter(pk=value).exists():
            raise serializers.ValidationError("Ce repas n’existe pas.")
        return value


class MealSectionSerializer(serializers.Serializer):
    """Un repas et ce qu'il contient ce jour-là."""

    meal_type = MealTypeSerializer(read_only=True)
    entries = DiaryEntrySerializer(many=True, read_only=True)
    totals = ComputedNutritionSerializer(read_only=True)
    incomplete_nutrients = serializers.ListField(child=serializers.CharField(), read_only=True)


class RemainingSerializer(serializers.Serializer):
    """Ce qu'il reste à consommer, dans les termes de l'objectif."""

    daily_calories = serializers.DecimalField(
        max_digits=9, decimal_places=2, read_only=True, allow_null=True
    )
    protein_g = serializers.DecimalField(
        max_digits=9, decimal_places=2, read_only=True, allow_null=True
    )
    carbs_g = serializers.DecimalField(
        max_digits=9, decimal_places=2, read_only=True, allow_null=True
    )
    fat_g = serializers.DecimalField(
        max_digits=9, decimal_places=2, read_only=True, allow_null=True
    )
    fiber_g = serializers.DecimalField(
        max_digits=9, decimal_places=2, read_only=True, allow_null=True
    )


class DiaryDaySerializer(serializers.Serializer):
    """Journée complète : objectifs, totaux et repas (spec 04 §4).

    Tout est renvoyé en un appel, pour que la page journal n'ait ni à enchaîner
    les requêtes ni à recalculer quoi que ce soit.
    """

    date = serializers.DateField(read_only=True)
    notes = serializers.CharField(read_only=True, allow_blank=True)
    goals = DailyValuesSerializer(read_only=True, allow_null=True)
    totals = ComputedNutritionSerializer(read_only=True)
    incomplete_nutrients = serializers.ListField(child=serializers.CharField(), read_only=True)
    remaining = RemainingSerializer(read_only=True, allow_null=True)
    meals = MealSectionSerializer(many=True, read_only=True)
