"""Serializers des objectifs nutritionnels."""

from datetime import date
from decimal import Decimal

from rest_framework import serializers

from accounts.models import ActivityLevel, GoalType, SexForCalculation
from accounts.serializers import validate_adult
from nutrition.models import MacroMode, NutritionGoal, NutritionGoalDayOverride, ValueSource
from nutrition.services.calculation import ESTIMATION_NOTICE

MACRO_FIELDS = ("daily_calories", "protein_g", "carbs_g", "fat_g", "fiber_g")


def validate_goal_consistency(
    *, goal_type: str, weight_kg: Decimal | None, target_weight_kg: Decimal | None
) -> None:
    """Refuse un objectif contredit par le poids cible."""
    if weight_kg is None or target_weight_kg is None:
        return

    if goal_type == GoalType.LOSS and target_weight_kg >= weight_kg:
        raise serializers.ValidationError(
            {"target_weight_kg": ["Un objectif de perte demande un poids cible inférieur."]}
        )
    if goal_type == GoalType.GAIN and target_weight_kg <= weight_kg:
        raise serializers.ValidationError(
            {"target_weight_kg": ["Un objectif de prise demande un poids cible supérieur."]}
        )


class CalorieCalculationSerializer(serializers.Serializer):
    """Entrées du calcul calorique — rien n'est persisté."""

    birth_date = serializers.DateField()
    sex_for_calculation = serializers.ChoiceField(choices=SexForCalculation.choices)
    height_cm = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal("50"))
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("20"))
    activity_level = serializers.ChoiceField(choices=ActivityLevel.choices)
    goal_type = serializers.ChoiceField(choices=GoalType.choices)
    goal_rate_kg_per_week = serializers.DecimalField(
        max_digits=4, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0")
    )
    target_weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True, min_value=Decimal("20")
    )

    def validate_birth_date(self, value: date) -> date:
        return validate_adult(value)

    def validate(self, attrs: dict) -> dict:
        validate_goal_consistency(
            goal_type=attrs["goal_type"],
            weight_kg=attrs.get("weight_kg"),
            target_weight_kg=attrs.get("target_weight_kg"),
        )
        return attrs


class CalorieEstimateSerializer(serializers.Serializer):
    """Résultat d'un calcul, avec ses avertissements et sa mention obligatoire."""

    bmr = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    tdee = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    daily_calories = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    protein_g = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    carbs_g = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    fat_g = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    warnings = serializers.ListField(child=serializers.CharField(), read_only=True)
    notice = serializers.CharField(read_only=True, default=ESTIMATION_NOTICE)


class DayOverrideSerializer(serializers.ModelSerializer):
    """Surcharge d'un jour de la semaine (0 = lundi)."""

    weekday_label = serializers.CharField(source="get_weekday_display_name", read_only=True)

    class Meta:
        model = NutritionGoalDayOverride
        fields = (
            "id",
            "weekday",
            "weekday_label",
            "daily_calories",
            "protein_g",
            "carbs_g",
            "fat_g",
            "fiber_g",
            "enabled",
        )
        read_only_fields = ("id", "weekday_label")

    def validate_weekday(self, value: int) -> int:
        if not 0 <= value <= 6:
            raise serializers.ValidationError("Le jour doit être compris entre 0 (lundi) et 6.")
        return value


class DailyValuesSerializer(serializers.Serializer):
    """Valeurs applicables à une date, surcharge de jour comprise.

    Les décimales passent par des `DecimalField` afin d'être sérialisées
    comme partout ailleurs dans l'API : en chaînes, sans conversion en
    flottant (spec 10 §2).
    """

    date = serializers.DateField(read_only=True)
    weekday = serializers.IntegerField(read_only=True)
    daily_calories = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    protein_g = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    carbs_g = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    fat_g = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    fiber_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True, allow_null=True
    )


class NutritionGoalSerializer(serializers.ModelSerializer):
    """Objectif nutritionnel.

    `net_carbs_g` et `macro_calories_gap` sont calculés à l'affichage : les
    calories restent la valeur de référence en cas d'incohérence (spec 01 §4).
    """

    day_overrides = DayOverrideSerializer(many=True, read_only=True)
    net_carbs_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True, allow_null=True
    )
    is_current = serializers.BooleanField(read_only=True)
    macro_calories_gap = serializers.SerializerMethodField()

    class Meta:
        model = NutritionGoal
        fields = (
            "id",
            "daily_calories",
            "protein_g",
            "carbs_g",
            "fat_g",
            "fiber_g",
            "net_carbs_g",
            "macro_mode",
            "calories_source",
            "macros_source",
            "start_date",
            "end_date",
            "is_current",
            "macro_calories_gap",
            "day_overrides",
            "created_at",
        )
        read_only_fields = ("id", "start_date", "end_date", "created_at")

    def get_macro_calories_gap(self, obj: NutritionGoal) -> Decimal:
        from nutrition.services.goals import macro_calorie_gap

        return macro_calorie_gap(
            {
                "daily_calories": obj.daily_calories,
                "protein_g": obj.protein_g,
                "carbs_g": obj.carbs_g,
                "fat_g": obj.fat_g,
            }
        )


class NutritionGoalWriteSerializer(serializers.Serializer):
    """Valeurs d'un objectif saisi ou recalculé."""

    daily_calories = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0")
    )
    protein_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    carbs_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    fat_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    fiber_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0")
    )
    macro_mode = serializers.ChoiceField(
        choices=MacroMode.choices, required=False, default=MacroMode.PERCENTAGE
    )
    calories_source = serializers.ChoiceField(
        choices=ValueSource.choices, required=False, default=ValueSource.MANUAL
    )
    macros_source = serializers.ChoiceField(
        choices=ValueSource.choices, required=False, default=ValueSource.MANUAL
    )
    start_date = serializers.DateField(required=False)


class OnboardingSerializer(CalorieCalculationSerializer):
    """Soumission complète de l'onboarding (spec 01 §2).

    Reprend les entrées du calcul et y ajoute les valeurs finalement retenues,
    que l'utilisateur a pu remplacer manuellement.
    """

    daily_calories = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0")
    )
    protein_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    carbs_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    fat_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    fiber_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0")
    )
    calories_source = serializers.ChoiceField(
        choices=ValueSource.choices, required=False, default=ValueSource.CALCULATED
    )
    macros_source = serializers.ChoiceField(
        choices=ValueSource.choices, required=False, default=ValueSource.CALCULATED
    )
