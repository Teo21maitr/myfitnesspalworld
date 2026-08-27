"""Serializers de la liste de courses (spec 04 §11)."""

from rest_framework import serializers

from planning.models import ShoppingList, ShoppingListItem, ShoppingVisibility


class ShoppingListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingListItem
        fields = (
            "id",
            "name",
            "food",
            "quantity",
            "unit_label",
            "is_checked",
            "sort_order",
            "source_type",
        )
        read_only_fields = ("id", "food", "source_type")


class ShoppingListItemWriteSerializer(serializers.Serializer):
    """Ajout manuel (spec 01 §16).

    La quantité est facultative : « du sel » est un article valable, et
    inventer « 1 unité » serait une donnée qu'on n'a pas (spec 01 §8).
    """

    name = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True
    )
    unit_label = serializers.CharField(
        max_length=40, required=False, allow_null=True, allow_blank=True
    )

    def validate_quantity(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return value


class ShoppingListSerializer(serializers.ModelSerializer):
    items = ShoppingListItemSerializer(many=True, read_only=True)
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingList
        fields = ("id", "name", "visibility", "items", "is_editable", "created_at", "updated_at")

    def get_is_editable(self, obj: ShoppingList) -> bool:
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)


class ShoppingListWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingList
        fields = ("id", "name", "visibility")
        read_only_fields = ("id",)


class GenerateSerializer(serializers.Serializer):
    """`POST /shopping-lists/generate/` (spec 04 §11).

    `meal_plan_id` n'est pas accepté : le planner n'existe pas, et un paramètre
    qui ne ferait rien vaudrait moins qu'une erreur claire.
    """

    shopping_list_id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=255, required=False)
    recipe_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    dates = serializers.ListField(child=serializers.DateField(), required=False)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("recipe_ids") and not attrs.get("dates"):
            raise serializers.ValidationError("Indiquez au moins une recette ou une journée.")
        return attrs


VISIBILITY_PRIVATE = ShoppingVisibility.PRIVATE
