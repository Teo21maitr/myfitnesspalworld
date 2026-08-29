"""Serializers du planning et de la liste de courses (spec 04 §8, §11)."""

from decimal import Decimal

from rest_framework import serializers

from planning.models import (
    MealPlan,
    MealPlanDay,
    MealPlanEntry,
    PlanEntryType,
    ShoppingList,
    ShoppingListItem,
    ShoppingVisibility,
)
from planning.services import plans


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
    """`POST /shopping-lists/generate/` (spec 04 §11)."""

    shopping_list_id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=255, required=False)
    recipe_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    dates = serializers.ListField(child=serializers.DateField(), required=False)
    meal_plan_id = serializers.IntegerField(required=False)

    def validate(self, attrs: dict) -> dict:
        if not any(attrs.get(source) for source in ("recipe_ids", "dates", "meal_plan_id")):
            raise serializers.ValidationError(
                "Indiquez au moins une recette, une journée ou un planning."
            )
        return attrs


VISIBILITY_PRIVATE = ShoppingVisibility.PRIVATE


# -----------------------------------------------------------------------------
# Planning (spec 04 §8)
# -----------------------------------------------------------------------------

#: La spec 01 §15 parle d'un jour, de plusieurs, ou d'une semaine : sept est
#: donc la borne naturelle.
#:
#: C'est aussi ce que le temps permet. Mesuré contre l'API : une journée coûte
#: une minute quand elle demande ses trois essais. Sept jours tiennent dans le
#: délai accordé à la tâche ; quatorze le dépasseraient.
MAX_PLAN_DAYS = 7


class MealPlanEntrySerializer(serializers.ModelSerializer):
    """Un élément planifié, avec son apport calculé sur les fiches courantes."""

    label = serializers.SerializerMethodField()
    values = serializers.SerializerMethodField()

    class Meta:
        model = MealPlanEntry
        fields = (
            "id",
            "meal_type",
            "entry_type",
            "food",
            "recipe",
            "quantity",
            "unit_label",
            "sort_order",
            "generated_by_ai",
            "label",
            "values",
        )

    def get_label(self, obj: MealPlanEntry) -> str:
        source = obj.food or obj.recipe
        return source.name if source is not None else "Élément indisponible"

    def get_values(self, obj: MealPlanEntry) -> dict[str, str | None]:
        values = plans.entry_values(obj)
        return {
            name: None if values.get(name) is None else str(values[name])
            for name in ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")
        }


class MealPlanDaySerializer(serializers.ModelSerializer):
    """Une journée du plan, avec ses totaux et son écart aux objectifs.

    L'écart est mesuré sur les fiches, jamais sur ce qu'un modèle a annoncé :
    c'est le seul chiffre qui ait servi à décider, et donc le seul à afficher.
    """

    entries = MealPlanEntrySerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()
    incomplete_nutrients = serializers.SerializerMethodField()
    targets = serializers.SerializerMethodField()
    deviations = serializers.SerializerMethodField()
    within_tolerance = serializers.SerializerMethodField()

    class Meta:
        model = MealPlanDay
        fields = (
            "id",
            "date",
            "entries",
            "totals",
            "incomplete_nutrients",
            "targets",
            "deviations",
            "within_tolerance",
        )

    def _nutrition(self, obj: MealPlanDay):
        cache = self.context.setdefault("_day_nutrition", {})
        if obj.pk not in cache:
            cache[obj.pk] = plans.day_nutrition(obj)
        return cache[obj.pk]

    def get_totals(self, obj: MealPlanDay) -> dict[str, str | None]:
        totals, _ = self._nutrition(obj)
        return {
            name: None if totals.get(name) is None else str(totals[name])
            for name in ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")
        }

    def get_incomplete_nutrients(self, obj: MealPlanDay) -> list[str]:
        _, incomplete = self._nutrition(obj)
        return incomplete

    def _targets(self, obj: MealPlanDay) -> dict | None:
        from nutrition.services.goals import resolve_for_date

        request = self.context.get("request")
        if request is None:
            return None
        return resolve_for_date(request.user, obj.date)

    def get_targets(self, obj: MealPlanDay) -> dict[str, str] | None:
        targets = self._targets(obj)
        if targets is None:
            return None
        return {
            name: str(targets[name])
            for name in ("daily_calories", "protein_g", "carbs_g", "fat_g")
            if targets.get(name) is not None
        }

    def _deviations(self, obj: MealPlanDay) -> dict[str, float]:
        from ai.services.meal_plan import deviations_from

        targets = self._targets(obj)
        if targets is None:
            return {}
        totals, _ = self._nutrition(obj)
        return deviations_from(totals, targets)

    def get_deviations(self, obj: MealPlanDay) -> dict[str, float]:
        return {name: round(value, 1) for name, value in self._deviations(obj).items()}

    def get_within_tolerance(self, obj: MealPlanDay) -> bool:
        """Calculé côté serveur, comme pour une proposition.

        Recopier les seuils dans le frontend les ferait diverger le jour où la
        spec 01 §15 changerait d'avis.
        """
        from ai.services.meal_plan import within_tolerance

        return within_tolerance(self._deviations(obj))


class MealPlanListSerializer(serializers.ModelSerializer):
    """Ligne de liste : ce qu'il faut pour choisir, pas davantage."""

    days_count = serializers.IntegerField(source="days.count", read_only=True)

    class Meta:
        model = MealPlan
        fields = (
            "id",
            "name",
            "start_date",
            "end_date",
            "generated_by_ai",
            "days_count",
            "created_at",
        )


class MealPlanSerializer(MealPlanListSerializer):
    days = MealPlanDaySerializer(many=True, read_only=True)

    class Meta(MealPlanListSerializer.Meta):
        fields = (*MealPlanListSerializer.Meta.fields, "notes", "days")


class PlanIngredientWriteSerializer(serializers.Serializer):
    food_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    unit_label = serializers.CharField(max_length=40)


class PlanRecipeWriteSerializer(serializers.Serializer):
    """Recette inédite retenue par l'utilisateur, créée à l'enregistrement."""

    name = serializers.CharField(max_length=255)
    servings = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("1"))
    instructions = serializers.CharField(allow_blank=True, required=False, default="")
    ingredients = PlanIngredientWriteSerializer(many=True, allow_empty=False)


class PlanEntryWriteSerializer(serializers.Serializer):
    meal_type_id = serializers.IntegerField()
    entry_type = serializers.ChoiceField(choices=PlanEntryType.choices)
    food_id = serializers.IntegerField(required=False)
    recipe_id = serializers.IntegerField(required=False)
    new_recipe = PlanRecipeWriteSerializer(required=False)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    unit_label = serializers.CharField(max_length=40)
    generated_by_ai = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: dict) -> dict:
        if attrs["entry_type"] == PlanEntryType.FOOD and not attrs.get("food_id"):
            raise serializers.ValidationError("Un aliment planifié doit désigner un aliment.")
        if attrs["entry_type"] == PlanEntryType.RECIPE and not (
            attrs.get("recipe_id") or attrs.get("new_recipe")
        ):
            raise serializers.ValidationError(
                "Une recette planifiée doit désigner une recette existante ou en décrire une."
            )
        return attrs


class PlanDayWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    entries = PlanEntryWriteSerializer(many=True, allow_empty=True)


class MealPlanWriteSerializer(serializers.Serializer):
    """`POST /meal-plans/` — enregistre un plan relu par l'utilisateur.

    C'est ici qu'une recette inventée devient une vraie recette : la génération
    ne fait que proposer (spec 07 §8).
    """

    name = serializers.CharField(max_length=255)
    notes = serializers.CharField(allow_blank=True, required=False, default="")
    generated_by_ai = serializers.BooleanField(required=False, default=False)
    days = PlanDayWriteSerializer(many=True, allow_empty=False)

    def validate_days(self, value: list) -> list:
        if len(value) > MAX_PLAN_DAYS:
            raise serializers.ValidationError(f"{MAX_PLAN_DAYS} journées au maximum.")
        if len({day["date"] for day in value}) != len(value):
            raise serializers.ValidationError("Une même date apparaît deux fois.")
        return value


class GeneratePlanSerializer(serializers.Serializer):
    """`POST /meal-plans/generate/` — les contraintes de la spec 01 §15."""

    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    meal_type_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list
    )
    liked = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list
    )
    disliked = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list
    )

    def validate(self, attrs: dict) -> dict:
        span = (attrs["end_date"] - attrs["start_date"]).days + 1
        if span < 1:
            raise serializers.ValidationError("La fin ne peut pas précéder le début.")
        if span > MAX_PLAN_DAYS:
            raise serializers.ValidationError(
                f"{MAX_PLAN_DAYS} journées au maximum : chacune coûte un appel au modèle."
            )
        return attrs


class RegenerateMealSerializer(serializers.Serializer):
    """`POST /meal-plans/{id}/regenerate-entry/` — le repas à recomposer."""

    day_id = serializers.IntegerField()
    meal_type_id = serializers.IntegerField()

    def validate(self, attrs: dict) -> dict:
        plan = self.context["plan"]
        if not plan.days.filter(pk=attrs["day_id"]).exists():
            raise serializers.ValidationError("Cette journée n'appartient pas au planning.")
        return attrs
