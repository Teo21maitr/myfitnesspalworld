"""Administration de l'IA (spec 05 §4)."""

from django.contrib import admin

from .models import AITaskLog


@admin.register(AITaskLog)
class AITaskLogAdmin(admin.ModelAdmin):
    """Journal des appels au fournisseur, en lecture seule.

    Rien n'y est modifiable : c'est une trace. Et rien n'y contient d'image, de
    prompt complet ni de donnée privée (spec 07 §10).
    """

    list_display = ("created_at", "task_type", "status", "provider", "model", "user")
    list_filter = ("task_type", "status", "provider", "created_at")
    search_fields = ("user__username", "model")
    ordering = ("-created_at",)
    readonly_fields = (
        "user",
        "task_type",
        "status",
        "provider",
        "model",
        "input_summary",
        "output_summary",
        "error_message",
        "cost_estimate",
        "created_at",
        "finished_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
