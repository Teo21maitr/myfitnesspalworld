"""Vues du journal (spec 04 §4 et §5).

Toutes les entrées sont filtrées par `diary_day__user` en base : aucune entrée
d'un autre compte n'est atteignable, même en devinant son identifiant
(spec 05 §12).
"""

from datetime import date as date_type

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from diary.models import DiaryEntry, EntryType, MealType
from diary.serializers import (
    BulkAddSerializer,
    CopyDaySerializer,
    CopyMealSerializer,
    DashboardSerializer,
    DiaryDaySerializer,
    DiaryEntrySerializer,
    DiaryEntryUpdateSerializer,
    DiaryEntryWriteSerializer,
    DuplicateEntrySerializer,
    MealTypeReorderSerializer,
    MealTypeSerializer,
)
from diary.services import copy as copy_service
from diary.services import day as day_service
from diary.services import entries as entries_service
from diary.services import meal_types as meal_types_service
from nutrition.models import Food
from nutrition.services.quantities import resolve_factor
from progress.services.summary import weight_summary

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]


def parse_date(raw: str | None) -> date_type:
    """Date demandée, aujourd'hui par défaut."""
    if not raw:
        return timezone.localdate()

    try:
        return date_type.fromisoformat(raw)
    except ValueError as error:
        raise ValidationError({"date": "Date invalide. Format attendu : AAAA-MM-JJ."}) from error


class DiaryDayView(APIView):
    """`GET /diary/?date=` — la journée entière en un appel."""

    permission_classes = ACTIVE_USER

    def get(self, request: Request) -> Response:
        day = parse_date(request.query_params.get("date"))
        return Response(DiaryDaySerializer(day_service.build_day(request.user, day)).data)


class DiaryEntryCreateView(APIView):
    """`POST /diary/entries/` — journalise un aliment ou un ajout rapide."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        serializer = DiaryEntryWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meal_type = MealType.objects.get(pk=data["meal_type_id"], user=request.user)
        consumed_at = serializer.resolve_consumed_at(data)

        if data["entry_type"] == EntryType.FOOD:
            food = serializer.resolve_food(data["food_id"])
            entry = entries_service.create_food_entry(
                user=request.user,
                food=food,
                day=data["date"],
                meal_type=meal_type,
                quantity=data["quantity"],
                unit_label=data["unit_label"],
                consumed_at=consumed_at,
                note=data["note"],
            )
        else:
            entry = entries_service.create_quick_add_entry(
                user=request.user,
                day=data["date"],
                meal_type=meal_type,
                consumed_at=consumed_at,
                values=data,
                note=data["note"],
            )

        return Response(DiaryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class DiaryEntryDetailView(APIView):
    """`PATCH` et `DELETE` sur une entrée existante."""

    permission_classes = ACTIVE_USER

    def get_object(self, request: Request, pk: int) -> DiaryEntry:
        entry = (
            DiaryEntry.objects.filter(diary_day__user=request.user, pk=pk)
            .select_related("meal_type", "food")
            .first()
        )
        if entry is None:
            raise NotFound("Cette entrée est introuvable.")
        return entry

    def patch(self, request: Request, pk: int) -> Response:
        entry = self.get_object(request, pk)
        serializer = DiaryEntryUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "unit_label" in data:
            # Changer d'unité impose de la réévaluer sur l'aliment. Quand
            # celui-ci a disparu, seule la quantité reste modifiable : l'entrée
            # garde le facteur figé à l'ajout.
            if entry.food is None:
                raise ValidationError(
                    {
                        "unit_label": (
                            "L’aliment d’origine n’existe plus : seule la quantité "
                            "peut être modifiée."
                        )
                    }
                )
            entry.snapshot_unit_factor = resolve_factor(entry.food, data["unit_label"])
            entry.unit_label = data["unit_label"]

        for field in ("quantity", "consumed_at", "note"):
            if field in data:
                setattr(entry, field, data[field])

        if "meal_type_id" in data:
            entry.meal_type = MealType.objects.get(pk=data["meal_type_id"], user=request.user)

        entry.save()
        return Response(DiaryEntrySerializer(entry).data)

    def delete(self, request: Request, pk: int) -> Response:
        self.get_object(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealTypeListCreateView(generics.ListCreateAPIView):
    """`GET` et `POST /meal-types/`."""

    serializer_class = MealTypeSerializer
    permission_classes = ACTIVE_USER
    pagination_class = None

    def get_queryset(self):
        return meal_types_service.meal_types_for(self.request.user).order_by("sort_order", "id")

    def perform_create(self, serializer) -> None:
        from django.utils.text import slugify

        name = serializer.validated_data["name"]
        last = self.get_queryset().last()
        serializer.save(
            user=self.request.user,
            slug=slugify(name)[:60],
            sort_order=(last.sort_order + 1) if last else 0,
        )


class MealTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET`, `PATCH` et `DELETE /meal-types/{id}/`.

    La suppression d'un repas système, ou d'un repas déjà utilisé, est une
    désactivation (spec 04 §5).
    """

    serializer_class = MealTypeSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return MealType.objects.filter(user=self.request.user)

    def perform_destroy(self, instance: MealType) -> None:
        meal_types_service.remove(instance)


class MealTypeReorderView(APIView):
    """`POST /meal-types/reorder/`."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        serializer = MealTypeReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meal_types_service.reorder(request.user, serializer.validated_data["ids"])

        queryset = meal_types_service.meal_types_for(request.user).order_by("sort_order", "id")
        return Response(MealTypeSerializer(queryset, many=True).data)


class DiaryEntryDuplicateView(APIView):
    """`POST /diary/entries/{id}/duplicate/` (spec 04 §4).

    La copie repart des valeurs actuelles de l'aliment, pas du snapshot de
    l'entrée d'origine (spec 01 §5).
    """

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        entry = _own_entry(request, pk)
        serializer = DuplicateEntrySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meal_type = None
        if "meal_type_id" in data:
            meal_type = MealType.objects.get(pk=data["meal_type_id"], user=request.user)

        copied = copy_service.copy_entry(
            user=request.user,
            entry=entry,
            day=data.get("date") or entry.diary_day.date,
            meal_type=meal_type,
        )

        return Response(DiaryEntrySerializer(copied).data, status=status.HTTP_201_CREATED)


class DiaryCopyMealView(APIView):
    """`POST /diary/copy-meal/` — un repas vers une ou plusieurs dates."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        serializer = CopyMealSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source_meal = MealType.objects.get(pk=data["source_meal_type_id"], user=request.user)
        target_meal = None
        if "target_meal_type_id" in data:
            target_meal = MealType.objects.get(pk=data["target_meal_type_id"], user=request.user)

        copied = copy_service.copy_meal(
            user=request.user,
            source_day=data["source_date"],
            source_meal_type=source_meal,
            target_days=data["target_dates"],
            target_meal_type=target_meal,
        )

        return Response(
            DiaryEntrySerializer(copied, many=True).data, status=status.HTTP_201_CREATED
        )


class DiaryCopyDayView(APIView):
    """`POST /diary/copy-day/` — une journée entière vers d'autres dates.

    La copie s'ajoute : les journées cibles conservent ce qu'elles contenaient.
    """

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        serializer = CopyDaySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        copied = copy_service.copy_day(
            user=request.user,
            source_day=data["source_date"],
            target_days=data["target_dates"],
        )

        return Response(
            DiaryEntrySerializer(copied, many=True).data, status=status.HTTP_201_CREATED
        )


class DiaryBulkAddView(APIView):
    """`POST /diary/bulk-add/` — un même aliment sur plusieurs dates."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        serializer = BulkAddSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        food = _visible_food(request, data["food_id"])
        meal_type = MealType.objects.get(pk=data["meal_type_id"], user=request.user)

        copied = copy_service.add_food_on_days(
            user=request.user,
            food=food,
            days=data["target_dates"],
            meal_type=meal_type,
            quantity=data["quantity"],
            unit_label=data["unit_label"],
            consumed_at=timezone.localtime(),
        )

        return Response(
            DiaryEntrySerializer(copied, many=True).data, status=status.HTTP_201_CREATED
        )


class DashboardView(APIView):
    """`GET /dashboard/?date=` — la journée, plus le poids (spec 04 §16).

    Passe par le même service que le journal : les deux écrans doivent afficher
    le même total pour la même date.
    """

    permission_classes = ACTIVE_USER

    def get(self, request: Request) -> Response:
        day = parse_date(request.query_params.get("date"))
        payload = day_service.build_day(request.user, day)
        payload["weight"] = weight_summary(request.user)

        return Response(DashboardSerializer(payload).data)


def _own_entry(request: Request, pk: int) -> DiaryEntry:
    """Entrée appartenant à l'appelant, sinon 404."""
    entry = (
        DiaryEntry.objects.filter(diary_day__user=request.user, pk=pk)
        .select_related("meal_type", "food", "diary_day")
        .first()
    )
    if entry is None:
        raise NotFound("Cette entrée est introuvable.")
    return entry


def _visible_food(request: Request, food_id: int) -> Food:
    """Aliment que l'appelant a le droit de consulter, sinon 400."""
    food = (
        Food.objects.visible_to(request.user)
        .select_related("nutrition")
        .prefetch_related("portions")
        .filter(pk=food_id)
        .first()
    )
    if food is None:
        raise ValidationError({"food_id": "Cet aliment est introuvable."})
    return food
