"""Vues du suivi de progression (spec 04 §14)."""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsActiveAccount
from progress.models import WeightEntry
from progress.serializers import WeightEntrySerializer


class WeightEntryListCreateView(generics.ListCreateAPIView):
    """`GET|POST /progress/weight/`.

    Une seule pesée par date : renvoyer sur une date existante met à jour la
    valeur au lieu d'échouer sur la contrainte d'unicité (spec 01 §19).
    """

    serializer_class = WeightEntrySerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return WeightEntry.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry, created = WeightEntry.objects.update_or_create(
            user=request.user,
            date=serializer.validated_data["date"],
            defaults={
                "weight_kg": serializer.validated_data["weight_kg"],
                "notes": serializer.validated_data.get("notes"),
            },
        )

        return Response(
            self.get_serializer(entry).data,
            status=201 if created else 200,
        )


class WeightEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /progress/weight/{id}/`."""

    serializer_class = WeightEntrySerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        # Filtrage par utilisateur : aucun accès horizontal possible.
        return WeightEntry.objects.filter(user=self.request.user)
