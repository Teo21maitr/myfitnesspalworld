"""Serializers des recettes et des repas enregistrés (spec 04 §6 et §7)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from nutrition.models import Food
from nutrition.models.nutrients import NUTRIENT_FIELDS
from nutrition.services.quantities import resolve_factor
from recipes.models import (
    ItemType,
    Recipe,
    RecipeIngredient,
    RecipeNutrition,
    RecipeVisibility,
    SavedMeal,
    SavedMealItem,
)
from recipes.services import nutrition as nutrition_service

SHARING_UNAVAILABLE = "Le partage à des utilisateurs précis n’est pas encore disponible."


def check_visibility(value: str) -> str:
    """Refuse `specific_users` tant que `SharePermission` n'existe pas."""
    if value == RecipeVisibility.SPECIFIC_USERS:
        raise serializers.ValidationError(SHARING_UNAVAILABLE)
    return value


def resolve_food(user, food_id: int) -> Food:
    """Aliment visible par l'appelant, jamais accepté du client sans contrôle."""
    food = (
        Food.objects.visible_to(user)
        .select_related("nutrition")
        .prefetch_related("portions")
        .filter(pk=food_id)
        .first()
    )
    if food is None:
        raise serializers.ValidationError({"food_id": "Aliment introuvable."})
    return food


def check_unit(food: Food, unit_label: str) -> None:
    """Refuse une unité que le backend ne saurait pas convertir (spec 01 §9)."""
    try:
        resolve_factor(food, unit_label)
    except DjangoValidationError as error:
        raise serializers.ValidationError(
            getattr(error, "message_dict", None) or {"unit_label": error.messages}
        ) from error


class RecipeNutritionSerializer(serializers.ModelSerializer):
    """Valeurs pour une portion, et nutriments partiels (spec 01 §8)."""

    # Propriété du modèle et non colonne : exposée pour que l'interface
    # affiche les recettes avec le même tableau que les aliments (spec 01 §4).
    net_carbs_g = serializers.DecimalField(max_digits=9, decimal_places=3, read_only=True)

    class Meta:
        model = RecipeNutrition
        fields = (*NUTRIENT_FIELDS, "net_carbs_g", "incomplete_nutrients")


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Ingrédient en lecture. `food` est nul si l'aliment a disparu."""

    class Meta:
        model = RecipeIngredient
        fields = ("id", "food", "food_name", "quantity", "unit_label", "sort_order")


class RecipeIngredientWriteSerializer(serializers.Serializer):
    food_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3)
    unit_label = serializers.CharField(max_length=40)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return value


class RecipeListSerializer(serializers.ModelSerializer):
    nutrition = RecipeNutritionSerializer(read_only=True)
    ingredient_count = serializers.IntegerField(source="ingredients.count", read_only=True)
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            "id",
            "name",
            "description",
            "servings",
            "visibility",
            "is_favorite",
            "nutrition",
            "ingredient_count",
            "is_editable",
            "created_at",
            "updated_at",
        )

    def get_is_editable(self, obj: Recipe) -> bool:
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)


class RecipeDetailSerializer(RecipeListSerializer):
    ingredients = RecipeIngredientSerializer(many=True, read_only=True)

    class Meta(RecipeListSerializer.Meta):
        fields = (*RecipeListSerializer.Meta.fields, "instructions", "ingredients")


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Création et modification. Les ingrédients sont remplacés en bloc.

    Un formulaire de recette soumet la composition entière : la remplacer d'un
    coup évite d'avoir à réconcilier des ajouts, des retraits et des
    réordonnancements partiels.
    """

    ingredients = RecipeIngredientWriteSerializer(many=True, required=False)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "name",
            "description",
            "instructions",
            "servings",
            "visibility",
            "is_favorite",
            "ingredients",
        )
        read_only_fields = ("id",)

    def validate_visibility(self, value: str) -> str:
        return check_visibility(value)

    def validate_servings(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le nombre de portions doit être positif.")
        return value

    def _write_ingredients(self, recipe: Recipe, rows: list[dict]) -> None:
        user = self.context["request"].user

        recipe.ingredients.all().delete()
        for order, row in enumerate(rows):
            food = resolve_food(user, row["food_id"])
            check_unit(food, row["unit_label"])
            RecipeIngredient.objects.create(
                recipe=recipe,
                food=food,
                food_name=food.name,
                quantity=row["quantity"],
                unit_label=row["unit_label"],
                sort_order=order,
            )

    @transaction.atomic
    def create(self, validated_data: dict) -> Recipe:
        rows = validated_data.pop("ingredients", [])
        recipe = Recipe.objects.create(owner=self.context["request"].user, **validated_data)
        self._write_ingredients(recipe, rows)
        nutrition_service.refresh(recipe)
        return recipe

    @transaction.atomic
    def update(self, instance: Recipe, validated_data: dict) -> Recipe:
        rows = validated_data.pop("ingredients", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if rows is not None:
            self._write_ingredients(instance, rows)

        # Le nombre de portions a pu changer sans que la composition bouge.
        nutrition_service.refresh(instance)
        return instance


class AddRecipeToDiarySerializer(serializers.Serializer):
    """`POST /recipes/{id}/add-to-diary/` (spec 04 §6)."""

    date = serializers.DateField()
    meal_type_id = serializers.IntegerField()
    servings = serializers.DecimalField(max_digits=10, decimal_places=3)
    consumed_at = serializers.DateTimeField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")

    def validate_servings(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le nombre de portions doit être positif.")
        return value


class SavedMealItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedMealItem
        fields = (
            "id",
            "item_type",
            "food",
            "recipe",
            "item_name",
            "quantity",
            "unit_label",
            "sort_order",
        )


class SavedMealItemWriteSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=ItemType.choices)
    food_id = serializers.IntegerField(required=False)
    recipe_id = serializers.IntegerField(required=False)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3)
    unit_label = serializers.CharField(max_length=40, required=False, default="portion")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["item_type"] == ItemType.FOOD and "food_id" not in attrs:
            raise serializers.ValidationError({"food_id": "Aliment requis."})
        if attrs["item_type"] == ItemType.RECIPE and "recipe_id" not in attrs:
            raise serializers.ValidationError({"recipe_id": "Recette requise."})
        return attrs


class SavedMealSerializer(serializers.ModelSerializer):
    items = SavedMealItemSerializer(many=True, read_only=True)
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = SavedMeal
        fields = (
            "id",
            "name",
            "description",
            "visibility",
            "items",
            "is_editable",
            "created_at",
            "updated_at",
        )

    def get_is_editable(self, obj: SavedMeal) -> bool:
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)


class SavedMealWriteSerializer(serializers.ModelSerializer):
    items = SavedMealItemWriteSerializer(many=True, required=False)

    class Meta:
        model = SavedMeal
        fields = ("id", "name", "description", "visibility", "items")
        read_only_fields = ("id",)

    def validate_visibility(self, value: str) -> str:
        return check_visibility(value)

    def _write_items(self, saved_meal: SavedMeal, rows: list[dict]) -> None:
        user = self.context["request"].user

        saved_meal.items.all().delete()
        for order, row in enumerate(rows):
            if row["item_type"] == ItemType.FOOD:
                food = resolve_food(user, row["food_id"])
                check_unit(food, row["unit_label"])
                SavedMealItem.objects.create(
                    saved_meal=saved_meal,
                    item_type=ItemType.FOOD,
                    food=food,
                    item_name=food.name,
                    quantity=row["quantity"],
                    unit_label=row["unit_label"],
                    sort_order=order,
                )
                continue

            recipe = Recipe.objects.visible_to(user).filter(pk=row["recipe_id"]).first()
            if recipe is None:
                raise serializers.ValidationError({"recipe_id": "Recette introuvable."})

            SavedMealItem.objects.create(
                saved_meal=saved_meal,
                item_type=ItemType.RECIPE,
                recipe=recipe,
                item_name=recipe.name,
                quantity=row["quantity"],
                # Une recette se compte en portions : aucune autre unité n'a de sens.
                unit_label="portion",
                sort_order=order,
            )

    @transaction.atomic
    def create(self, validated_data: dict) -> SavedMeal:
        rows = validated_data.pop("items", [])
        saved_meal = SavedMeal.objects.create(owner=self.context["request"].user, **validated_data)
        self._write_items(saved_meal, rows)
        return saved_meal

    @transaction.atomic
    def update(self, instance: SavedMeal, validated_data: dict) -> SavedMeal:
        rows = validated_data.pop("items", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if rows is not None:
            self._write_items(instance, rows)

        return instance


class AddSavedMealToDiarySerializer(serializers.Serializer):
    """`POST /saved-meals/{id}/add-to-diary/` (spec 04 §7)."""

    date = serializers.DateField()
    meal_type_id = serializers.IntegerField()
    consumed_at = serializers.DateTimeField(required=False)
