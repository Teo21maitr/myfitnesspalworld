"""Administration des objectifs nutritionnels.

En lecture seule : les objectifs appartiennent à l'utilisateur et se
modifient depuis l'application, l'admin sert au support (spec 05 §4).
"""

from django.contrib import admin

from .models import Food, FoodNutrition, FoodPortion, NutritionGoal, NutritionGoalDayOverride


class DayOverrideInline(admin.TabularInline):
    model = NutritionGoalDayOverride
    extra = 0
    can_delete = False
    readonly_fields = (
        "weekday",
        "daily_calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "enabled",
    )

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(NutritionGoal)
class NutritionGoalAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "daily_calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "start_date",
        "end_date",
    )
    list_filter = ("calories_source", "macros_source", "macro_mode", "start_date")
    search_fields = ("user__username", "user__normalized_username")
    ordering = ("-start_date",)
    inlines = (DayOverrideInline,)
    # Tous les champs sont en lecture seule.
    readonly_fields = tuple(field.name for field in NutritionGoal._meta.fields)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class FoodNutritionInline(admin.StackedInline):
    model = FoodNutrition
    can_delete = False
    extra = 0


class FoodPortionInline(admin.TabularInline):
    model = FoodPortion
    extra = 0


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    """Référentiel d'aliments.

    L'administrateur peut désactiver une fiche importée mais pas la modifier :
    les données Ciqual et Open Food Facts appartiennent à leur source
    (spec 05 §6, spec 11 §2).
    """

    list_display = ("name", "brand", "source", "is_active", "is_verified", "owner")
    list_filter = ("source", "is_active", "is_verified", "visibility")
    search_fields = ("name", "brand", "barcode", "external_id", "search_text")
    ordering = ("name",)
    readonly_fields = ("search_text", "external_id", "created_at", "updated_at")
    inlines = (FoodNutritionInline, FoodPortionInline)
    actions = ("deactivate_foods", "activate_foods")

    @admin.action(description="Désactiver les aliments sélectionnés")
    def deactivate_foods(self, request, queryset) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} aliment(s) désactivé(s).")

    @admin.action(description="Réactiver les aliments sélectionnés")
    def activate_foods(self, request, queryset) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} aliment(s) réactivé(s).")
