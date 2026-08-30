"""Vues du suivi de progression (spec 04 §14)."""

from datetime import date as date_type

from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.dates import parse_period as shared_parse_period
from common.permissions import IsActiveAccount
from common.uploads import read_image
from progress.models import (
    BodyMeasurementEntry,
    PhotoType,
    ProgressPhoto,
    ProgressPhotoGroup,
    WeightEntry,
)
from progress.serializers import (
    BodyMeasurementEntrySerializer,
    ChartSeriesSerializer,
    ProgressPhotoGroupSerializer,
    WeightEntrySerializer,
)
from progress.services import charts, photo_storage
from progress.services import photos as photos_service


class StorageDisabled(APIException):
    """Le stockage objet n'est pas configuré.

    503 plutôt que 500 : ce n'est pas une panne mais une fonctionnalité non
    branchée, et le reste de l'application continue de fonctionner.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Le stockage des photos n'est pas configuré."
    default_code = "storage_unavailable"


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
    """Intervalle des courbes : 90 jours par défaut, deux ans au maximum."""
    return shared_parse_period(
        raw_from,
        raw_to,
        default_days=charts.DEFAULT_PERIOD_DAYS,
        max_days=charts.MAX_PERIOD_DAYS,
    )


#: Quatre angles, donc quatre photos par envoi (spec 01 §20).
MAX_PHOTOS = 4

PHOTOS_FIELD = "photos"


class ProgressPhotoListCreateView(generics.ListCreateAPIView):
    """`GET|POST /progress/photos/` (spec 04 §15).

    `POST` reçoit du multipart : la date et ses métadonnées, puis les fichiers
    sous `photos` et leurs angles sous `photo_types`, dans le même ordre.

    Une date déjà photographiée est **complétée**, pas remplacée : on peut
    revenir ajouter le profil après la face.
    """

    serializer_class = ProgressPhotoGroupSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # Filtrage par utilisateur : aucun accès horizontal possible.
        return (
            ProgressPhotoGroup.objects.filter(user=self.request.user)
            .prefetch_related("photos")
            .order_by("-date")
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        if not photo_storage.is_configured():
            # Le stockage manque : seule la photo est refusée, le reste de
            # l'application n'en est pas affecté (spec 07 §11, même principe).
            raise StorageDisabled

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploads = request.FILES.getlist(PHOTOS_FIELD)
        types = request.data.getlist("photo_types") if hasattr(request.data, "getlist") else []
        images = read_photo_uploads(uploads, types)

        values = dict(serializer.validated_data)
        group, _ = ProgressPhotoGroup.objects.get_or_create(
            user=request.user, date=values.pop("date"), defaults=values
        )

        for photo_type, data in images:
            photos_service.store_photo(group, data=data, photo_type=photo_type)

        group.refresh_from_db()
        return Response(
            self.get_serializer(group).data,
            status=status.HTTP_201_CREATED,
        )


class ProgressPhotoGroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /progress/photos/{id}/`.

    `PATCH` ne touche qu'aux métadonnées. La suppression emporte les objets du
    stockage, pas seulement les lignes (spec 01 §20).
    """

    serializer_class = ProgressPhotoGroupSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return ProgressPhotoGroup.objects.filter(user=self.request.user).prefetch_related("photos")

    def perform_destroy(self, instance: ProgressPhotoGroup) -> None:
        photos_service.delete_group(instance)


class ProgressPhotoDetailView(APIView):
    """`DELETE /progress/photos/{id}/files/{photo_id}/`.

    La spec 04 §15 dit « supprimer/réuploader pour remplacer » sans donner de
    route pour retirer une seule photo d'une date : la voici.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def delete(self, request: Request, pk: int, photo_id: int) -> Response:
        photo = ProgressPhoto.objects.filter(
            pk=photo_id, group__pk=pk, group__user=request.user
        ).first()
        if photo is None:
            raise NotFound("Photo introuvable.")

        photos_service.delete_photo(photo)
        return Response(status=status.HTTP_204_NO_CONTENT)


def read_photo_uploads(uploads: list, types: list[str]) -> list[tuple[str, bytes]]:
    """Valide les fichiers et les apparie à leurs angles.

    Un angle absent vaut « autre » plutôt que de faire échouer l'envoi : la
    photo compte plus que son étiquette, et l'étiquette se corrige.
    """
    if not uploads:
        raise ValidationError({PHOTOS_FIELD: ["Ajoutez au moins une photo."]})

    if len(uploads) > MAX_PHOTOS:
        raise ValidationError({PHOTOS_FIELD: [f"{MAX_PHOTOS} photos au maximum."]})

    valid = set(PhotoType.values)
    images = []

    for index, upload in enumerate(uploads):
        _, data = read_image(upload, field=PHOTOS_FIELD)
        wanted = types[index] if index < len(types) else PhotoType.OTHER
        images.append((wanted if wanted in valid else PhotoType.OTHER, data))

    return images
