"""Administration des recettes et des repas enregistrés."""

from django.contrib import admin

from .models import Recipe, RecipeIngredient, SavedMeal, SavedMealItem


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    fields = ("food_name", "food", "quantity", "unit_label", "sort_order")
    readonly_fields = fields


class SavedMealItemInline(admin.TabularInline):
    model = SavedMealItem
    extra = 0
    fields = ("item_type", "item_name", "food", "recipe", "quantity", "unit_label", "sort_order")
    readonly_fields = fields


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Consultation : les recettes se composent depuis l'application."""

    list_display = ("name", "owner", "servings", "visibility", "is_favorite", "deleted_at")
    list_filter = ("visibility", "is_favorite")
    search_fields = ("name", "owner__username")
    ordering = ("name",)
    inlines = [RecipeIngredientInline]
    readonly_fields = ("owner", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(SavedMeal)
class SavedMealAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "visibility", "deleted_at")
    list_filter = ("visibility",)
    search_fields = ("name", "owner__username")
    ordering = ("name",)
    inlines = [SavedMealItemInline]
    readonly_fields = ("owner", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False
