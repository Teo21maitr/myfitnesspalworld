"""Serializers des notifications, préférences et rappels (spec 04 §19)."""

from rest_framework import serializers

from notifications.models import EventType, Notification, Reminder, ReminderType


class NotificationSerializer(serializers.ModelSerializer):
    """Une notification interne.

    `reminder` et `scheduled_on` ne sortent pas : ce sont les rouages de
    l'idempotence, pas une information pour le lecteur.
    """

    event_label = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "event_type",
            "event_label",
            "title",
            "message",
            "link",
            "is_read",
            "created_at",
        )
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.Serializer):
    """Préférences d'un type d'événement.

    Un `Serializer` nu et non un `ModelSerializer` : la réponse porte les six
    types, y compris ceux qui n'ont **aucune ligne** en base (spec 01 §24).
    """

    event_type = serializers.ChoiceField(choices=EventType.choices)
    event_label = serializers.CharField(read_only=True)
    in_app_enabled = serializers.BooleanField()
    email_enabled = serializers.BooleanField()
    push_enabled = serializers.BooleanField(read_only=True)


class ReminderSerializer(serializers.ModelSerializer):
    """Un rappel. Un seul par type, la base le garantit."""

    reminder_type = serializers.ChoiceField(choices=ReminderType.choices)
    type_label = serializers.CharField(source="get_reminder_type_display", read_only=True)

    class Meta:
        model = Reminder
        fields = (
            "id",
            "reminder_type",
            "type_label",
            "time",
            "days_of_week",
            "enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "type_label", "created_at", "updated_at")

    def validate_days_of_week(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Choisissez au moins un jour.")

        if any(not isinstance(day, int) or not 0 <= day <= 6 for day in value):
            raise serializers.ValidationError("Jours attendus entre 0 (lundi) et 6 (dimanche).")

        # Dédoublonné et trié : deux fois le même jour ne change rien, mais
        # ferait deux lignes différentes pour un même réglage.
        return sorted(set(value))
