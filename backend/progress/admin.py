"""Administration du suivi de progression."""

from django.contrib import admin

from .models import WeightEntry


@admin.register(WeightEntry)
class WeightEntryAdmin(admin.ModelAdmin):
    """Lecture seule : les pesées se saisissent depuis l'application."""

    list_display = ("user", "date", "weight_kg")
    list_filter = ("date",)
    search_fields = ("user__username", "user__normalized_username")
    ordering = ("-date",)
    readonly_fields = ("user", "date", "weight_kg", "notes", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
