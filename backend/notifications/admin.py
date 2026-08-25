"""Administration des notifications."""

from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """Journal des emails transactionnels, en lecture seule (spec 05 §4)."""

    list_display = ("created_at", "email_type", "recipient", "status", "user")
    list_filter = ("email_type", "status", "created_at")
    search_fields = ("recipient", "user__username")
    ordering = ("-created_at",)
    readonly_fields = (
        "user",
        "email_type",
        "recipient",
        "status",
        "provider_response_summary",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
