"""Vues du suivi de progression (spec 04 §14)."""

from datetime import date as date_type
from datetime import timedelta

from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from progress.models import BodyMeasurementEntry, WeightEntry
from progress.serializers import (
    BodyMeasurementEntrySerializer,
    ChartSeriesSerializer,
    WeightEntrySerializer,
)
from progress.services import charts


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


class BodyMeasurementListCreateView(generics.ListCreateAPIView):
    """`GET|POST /progress/measurements/`.

    Comme pour le poids, une seconde saisie sur une date existante met à jour
    l'entrée au lieu d'échouer sur la contrainte d'unicité (spec 01 §19).
    Seules les mesures présentes dans le corps sont remplacées : les autres
    gardent leur valeur, faute de quoi enregistrer un tour de taille effacerait
    la masse grasse relevée le même jour.
    """

    serializer_class = BodyMeasurementEntrySerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return BodyMeasurementEntry.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        values = dict(serializer.validated_data)
        entry, created = BodyMeasurementEntry.objects.update_or_create(
            user=request.user,
            date=values.pop("date"),
            defaults=values,
        )

        return Response(
            self.get_serializer(entry).data,
            status=201 if created else 200,
        )


class BodyMeasurementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /progress/measurements/{id}/`."""

    serializer_class = BodyMeasurementEntrySerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        # Filtrage par utilisateur : aucun accès horizontal possible.
        return BodyMeasurementEntry.objects.filter(user=self.request.user)


class ProgressChartView(APIView):
    """`GET /progress/charts/?from=&to=&metric=` (spec 04 §14).

    Endpoint distinct de `/progress/weight/`, qui est paginé à 25 : une courbe
    construite sur la première page serait tronquée sans le dire. La série
    entière de l'intervalle est renvoyée d'un bloc, d'où la période bornée.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request: Request) -> Response:
        metric = request.query_params.get("metric") or "weight"
        if metric not in charts.METRICS:
            accepted = ", ".join(charts.METRICS)
            raise ValidationError({"metric": f"Métrique inconnue. Valeurs acceptées : {accepted}."})

        start, end = parse_period(
            request.query_params.get("from"),
            request.query_params.get("to"),
        )

        data = charts.series(request.user, metric, start, end)
        return Response(ChartSeriesSerializer(data).data)


def parse_period(raw_from: str | None, raw_to: str | None) -> tuple[date_type, date_type]:
    """Intervalle demandé, borné pour que la réponse reste finie."""
    end = parse_date(raw_to, "to") or timezone.localdate()
    start = parse_date(raw_from, "from") or end - timedelta(days=charts.DEFAULT_PERIOD_DAYS - 1)

    if start > end:
        raise ValidationError({"from": "La date de début doit précéder la date de fin."})

    if (end - start).days + 1 > charts.MAX_PERIOD_DAYS:
        raise ValidationError({"from": "Période trop longue : deux ans au maximum."})

    return start, end


def parse_date(raw: str | None, field: str) -> date_type | None:
    """Date d'un paramètre de requête, `None` s'il est absent."""
    if not raw:
        return None

    try:
        return date_type.fromisoformat(raw)
    except ValueError as error:
        raise ValidationError({field: "Date invalide. Format attendu : AAAA-MM-JJ."}) from error
