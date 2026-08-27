"""Serializers du référentiel d'aliments (spec 04 §3).

Une valeur nutritionnelle absente est sérialisée `null` et jamais `0` : c'est
au frontend de l'afficher « — » (spec 01 §8).
"""

from rest_framework import serializers

from nutrition.models import (
    Food,
    FoodNutrition,
    FoodPortion,
    FoodSource,
    FoodVisibility,
    UnitType,
)
from nutrition.services.quantities import available_units as food_available_units
from social.models import ResourceType
from social.services.sharing import revoke_resource

NUTRITION_FIELDS = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
    "fiber_g",
    "sugars_g",
    "sodium_mg",
    "salt_g",
    "cholesterol_mg",
    "potassium_mg",
    "calcium_mg",
    "iron_mg",
    "magnesium_mg",
    "vitamin_a_ug",
    "vitamin_b6_mg",
    "vitamin_b12_ug",
    "vitamin_c_mg",
    "vitamin_d_ug",
    "vitamin_e_mg",
    "vitamin_k_ug",
)


class FoodNutritionSerializer(serializers.ModelSerializer):
    """Valeurs pour la quantité de référence de l'aliment."""

    net_carbs_g = serializers.DecimalField(
        max_digits=9, decimal_places=3, read_only=True, allow_null=True
    )

    class Meta:
        model = FoodNutrition
        fields = (*NUTRITION_FIELDS, "net_carbs_g")


class FoodPortionSerializer(serializers.ModelSerializer):
    """Portion d'un aliment.

    `is_own` indique une portion ajoutée par l'utilisateur courant : lui seul
    la voit et peut la modifier (spec 01 §9).
    """

    is_own = serializers.SerializerMethodField()

    class Meta:
        model = FoodPortion
        fields = (
            "id",
            "name",
            "gram_equivalent",
            "milliliter_equivalent",
            "unit_equivalent",
            "is_default",
            "sort_order",
            "is_own",
        )
        read_only_fields = ("id", "is_own")

    def get_is_own(self, obj: FoodPortion) -> bool:
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)

    def validate(self, attrs: dict) -> dict:
        equivalents = (
            attrs.get("gram_equivalent"),
            attrs.get("milliliter_equivalent"),
            attrs.get("unit_equivalent"),
        )
        if all(value is None for value in equivalents):
            raise serializers.ValidationError(
                "Indiquez au moins un équivalent en grammes, millilitres ou unités."
            )
        return attrs


class FoodListSerializer(serializers.ModelSerializer):
    """Ligne de résultat de recherche (spec 06 §7).

    Volontairement légère : nom, marque, énergie, source et favori suffisent à
    l'affichage d'une liste.
    """

    source_label = serializers.CharField(source="get_source_display", read_only=True)
    energy_kcal = serializers.DecimalField(
        source="nutrition.energy_kcal",
        max_digits=9,
        decimal_places=3,
        read_only=True,
        allow_null=True,
    )
    is_favorite = serializers.BooleanField(read_only=True, default=False)
    is_own = serializers.SerializerMethodField()

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
            "energy_kcal",
            "is_favorite",
            "is_own",
            "is_verified",
        )

    def get_is_own(self, obj: Food) -> bool:
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)


class FoodDetailSerializer(FoodListSerializer):
    """Fiche complète d'un aliment."""

    nutrition = FoodNutritionSerializer(read_only=True)
    portions = serializers.SerializerMethodField()
    is_editable = serializers.SerializerMethodField()
    available_units = serializers.SerializerMethodField()

    class Meta(FoodListSerializer.Meta):
        fields = (
            *FoodListSerializer.Meta.fields,
            "barcode",
            "visibility",
            "default_unit_type",
            "nutrition",
            "portions",
            "available_units",
            "is_editable",
            "created_at",
            "updated_at",
        )

    def get_portions(self, obj: Food) -> list[dict]:
        """Portions officielles, plus celles de l'utilisateur courant."""
        request = self.context.get("request")
        user_id = request.user.id if request else None

        portions = [
            portion
            for portion in obj.portions.all()
            if portion.owner_id is None or portion.owner_id == user_id
        ]
        return FoodPortionSerializer(portions, many=True, context=self.context).data

    def get_available_units(self, obj: Food) -> list[str]:
        """Unités réellement calculables pour cet aliment (spec 01 §9).

        Exposées afin que le formulaire d'ajout au journal n'en propose jamais
        une que le backend refuserait, faute de densité connue.
        """
        return food_available_units(obj)

    def get_is_editable(self, obj: Food) -> bool:
        request = self.context.get("request")
        return bool(request and obj.source == FoodSource.USER and obj.owner_id == request.user.id)


class FoodWriteSerializer(serializers.ModelSerializer):
    """Création et modification d'un aliment personnel (spec 01 §11).

    La source et le propriétaire ne sont jamais acceptés depuis le client : un
    utilisateur ne crée que ses propres aliments (spec 05 §12).
    """

    nutrition = FoodNutritionSerializer()

    class Meta:
        model = Food
        fields = (
            "id",
            "name",
            "brand",
            "barcode",
            "visibility",
            "default_unit_type",
            "reference_amount",
            "reference_unit",
            "nutrition",
        )
        read_only_fields = ("id",)

    def validate_reference_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("La quantité de référence doit être positive.")
        return value

    def validate(self, attrs: dict) -> dict:
        nutrition = attrs.get("nutrition")

        # Sur une modification partielle qui ne touche pas à la nutrition, il
        # n'y a rien à vérifier ici.
        if nutrition is None:
            if self.instance is None:
                raise serializers.ValidationError(
                    {"nutrition": ["Les valeurs nutritionnelles sont obligatoires."]}
                )
            return attrs

        if nutrition.get("energy_kcal") is None:
            raise serializers.ValidationError(
                {"nutrition": {"energy_kcal": ["L’énergie est obligatoire."]}}
            )
        return attrs

    def create(self, validated_data: dict) -> Food:
        nutrition_data = validated_data.pop("nutrition")
        food = Food.objects.create(
            **validated_data,
            source=FoodSource.USER,
            owner=self.context["request"].user,
            default_unit_type=validated_data.get("default_unit_type", UnitType.GRAM),
        )
        FoodNutrition.objects.create(food=food, **nutrition_data)
        return food

    def update(self, instance: Food, validated_data: dict) -> Food:
        nutrition_data = validated_data.pop("nutrition", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if instance.visibility == FoodVisibility.PRIVATE:
            # Déclarer « privé » referme les partages déjà accordés : les deux
            # ne peuvent pas dire le contraire l'un de l'autre.
            revoke_resource(ResourceType.FOOD, instance.pk)

        if nutrition_data is not None:
            nutrition, _ = FoodNutrition.objects.get_or_create(food=instance)
            for field, value in nutrition_data.items():
                setattr(nutrition, field, value)
            nutrition.save()

        return instance


class ExternalFoodCandidateSerializer(serializers.Serializer):
    """Résultat de recherche Open Food Facts, avant tout enregistrement.

    Volontairement pauvre : la recherche sert à choisir un produit, pas à
    l'afficher. Les valeurs nutritionnelles viennent ensuite de l'endpoint
    produit, seul à faire autorité (spec 11 §3).
    """

    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    brand = serializers.CharField(read_only=True, allow_blank=True)
    #: Renseigné quand le produit est déjà en base : l'interface peut ouvrir sa
    #: fiche sans consommer de quota.
    food_id = serializers.IntegerField(read_only=True, allow_null=True)
