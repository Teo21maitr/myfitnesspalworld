"""Administration du suivi de progression."""

from django.contrib import admin

from .models import (
    MEASUREMENT_FIELDS,
    BodyMeasurementEntry,
    ProgressPhoto,
    ProgressPhotoGroup,
    WeightEntry,
)


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


@admin.register(BodyMeasurementEntry)
class BodyMeasurementEntryAdmin(admin.ModelAdmin):
    """Lecture seule : les mensurations se saisissent depuis l'application."""

    list_display = ("user", "date", "waist_cm", "hips_cm", "body_fat_percent")
    list_filter = ("date",)
    search_fields = ("user__username", "user__normalized_username")
    ordering = ("-date",)
    readonly_fields = (
        "user",
        "date",
        *MEASUREMENT_FIELDS,
        "notes",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class ProgressPhotoInline(admin.TabularInline):
    """Les photos d'un groupe, sans jamais montrer leur clé.

    La clé est non devinable, donc un secret d'accès : l'afficher ici la
    livrerait à qui consulte l'admin (spec 05 §10 et §15).
    """

    model = ProgressPhoto
    extra = 0
    fields = ("photo_type", "mime_type", "size_bytes", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ProgressPhotoGroup)
class ProgressPhotoGroupAdmin(admin.ModelAdmin):
    """Consultation seule, comme les pesées et les mensurations.

    L'image elle-même n'est pas affichée : l'admin peut avoir à constater qu'un
    groupe existe, jamais à regarder les photos de quelqu'un.
    """

    list_display = ("user", "date", "photo_count", "weight_kg_snapshot")
    list_filter = ("date",)
    search_fields = ("user__username",)
    date_hierarchy = "date"
    inlines = [ProgressPhotoInline]
    readonly_fields = ("user", "date", "weight_kg_snapshot", "notes", "created_at", "updated_at")

    @admin.display(description="photos")
    def photo_count(self, obj: ProgressPhotoGroup) -> int:
        return obj.photos.count()

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
