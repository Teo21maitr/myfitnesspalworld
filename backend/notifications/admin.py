"""Administration des notifications."""

from django.contrib import admin

from .models import EmailLog, Notification, Reminder


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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Consultation seule : une notification se lit dans l'application."""

    list_display = ("user", "event_type", "title", "is_read", "created_at")
    list_filter = ("event_type", "is_read")
    search_fields = ("user__username", "title")
    date_hierarchy = "created_at"
    readonly_fields = (
        "user",
        "event_type",
        "title",
        "message",
        "link",
        "is_read",
        "reminder",
        "scheduled_on",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    """Consultation seule : un rappel se règle depuis l'application."""

    list_display = ("user", "reminder_type", "time", "enabled")
    list_filter = ("reminder_type", "enabled")
    search_fields = ("user__username",)
    readonly_fields = (
        "user",
        "reminder_type",
        "time",
        "days_of_week",
        "enabled",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
