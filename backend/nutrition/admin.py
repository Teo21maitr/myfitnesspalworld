"""Administration des objectifs nutritionnels.

En lecture seule : les objectifs appartiennent à l'utilisateur et se
modifient depuis l'application, l'admin sert au support (spec 05 §4).
"""

from django.contrib import admin

from .models import NutritionGoal, NutritionGoalDayOverride


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
