"""Administration de l'infrastructure partagée."""

from django.contrib import admin

from .models import AppSetting, AsyncTask


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    """Réglages globaux, modifiables (spec 05 §4).

    C'est ici que se coupe l'IA sans redéploiement : la clé `ai_enabled` à
    `false` suffit (spec 07 §11).
    """

    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "description")
    ordering = ("key",)


@admin.register(AsyncTask)
class AsyncTaskAdmin(admin.ModelAdmin):
    """Tâches longues, en lecture seule : elles se pilotent par le code."""

    list_display = ("created_at", "task_type", "status", "progress", "user", "expires_at")
    list_filter = ("task_type", "status", "created_at")
    search_fields = ("user__username",)
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "user",
        "task_type",
        "status",
        "progress",
        "result",
        "error",
        "created_at",
        "updated_at",
        "expires_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
