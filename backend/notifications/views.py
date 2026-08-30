"""Vues des notifications, préférences et rappels (spec 04 §19)."""

from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from notifications.models import EventType, Notification, NotificationPreference, Reminder
from notifications.serializers import (
    NotificationPreferenceSerializer,
    NotificationSerializer,
    ReminderSerializer,
)
from notifications.services import dispatch

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]


class NotificationListView(generics.ListAPIView):
    """`GET /notifications/` — les siennes, les plus récentes d'abord."""

    serializer_class = NotificationSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        # Filtrage par utilisateur : aucun accès horizontal possible.
        return Notification.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Le compteur voyage avec la liste : l'interface en a besoin pour sa
        # pastille, et une seconde requête pour un entier serait du gâchis.
        response.data["unread"] = dispatch.unread_count(request.user)
        return response


class NotificationReadView(APIView):
    """`POST /notifications/{id}/read/`."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        notification = Notification.objects.filter(pk=pk, user=request.user).first()
        if notification is None:
            # 404 et non 403 : confirmer l'existence renseignerait déjà.
            raise NotFound("Notification introuvable.")

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])

        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    """`POST /notifications/read-all/`."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"updated": updated})


class NotificationPreferenceView(APIView):
    """`GET|PATCH /notification-preferences/` (spec 04 §19).

    La lecture rend **les six types**, défauts compris, même sans ligne en
    base : une préférence absente n'est pas une préférence, et l'interface ne
    doit pas avoir à deviner.
    """

    permission_classes = ACTIVE_USER

    def get(self, request: Request) -> Response:
        return Response({"results": self._rows(request.user)})

    def patch(self, request: Request) -> Response:
        entries = request.data.get("results", request.data)
        if not isinstance(entries, list):
            raise ValidationError({"results": ["Une liste de préférences est attendue."]})

        serializer = NotificationPreferenceSerializer(data=entries, many=True)
        serializer.is_valid(raise_exception=True)

        for values in serializer.validated_data:
            NotificationPreference.objects.update_or_create(
                user=request.user,
                event_type=values["event_type"],
                defaults={
                    "in_app_enabled": values["in_app_enabled"],
                    "email_enabled": values["email_enabled"],
                },
            )

        return Response({"results": self._rows(request.user)})

    def _rows(self, user) -> list[dict]:
        labels = dict(EventType.choices)
        return [
            {
                "event_type": event_type,
                "event_label": labels[event_type],
                "in_app_enabled": channels.in_app,
                "email_enabled": channels.email,
                "push_enabled": channels.push,
            }
            for event_type, channels in dispatch.preferences_for(user).items()
        ]


class ReminderListCreateView(generics.ListCreateAPIView):
    """`GET|POST /reminders/`.

    La spec 04 §19 ne prévoyait aucune route pour régler un rappel, alors que
    la spec 01 §24 en décrit le comportement et la spec 03 §11 le modèle.

    Un second envoi sur un type déjà réglé **met à jour** plutôt que d'échouer
    sur la contrainte d'unicité : « un seul rappel par type » se règle, il ne
    se refuse pas.
    """

    serializer_class = ReminderSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        values = dict(serializer.validated_data)
        reminder, created = Reminder.objects.update_or_create(
            user=request.user,
            reminder_type=values.pop("reminder_type"),
            defaults=values,
        )

        return Response(
            self.get_serializer(reminder).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ReminderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /reminders/{id}/`."""

    serializer_class = ReminderSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)
