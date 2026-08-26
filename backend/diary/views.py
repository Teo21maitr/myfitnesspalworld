"""Vues du journal (spec 04 §4 et §5).

Toutes les entrées sont filtrées par `diary_day__user` en base : aucune entrée
d'un autre compte n'est atteignable, même en devinant son identifiant
(spec 05 §12).
"""

from datetime import date as date_type
from decimal import Decimal

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from diary.models import DiaryDay, DiaryEntry, EntryType, MealType
from diary.serializers import (
    DiaryDaySerializer,
    DiaryEntrySerializer,
    DiaryEntryUpdateSerializer,
    DiaryEntryWriteSerializer,
    MealTypeReorderSerializer,
    MealTypeSerializer,
)
from diary.services import entries as entries_service
from diary.services import meal_types as meal_types_service
from nutrition.services.goals import resolve_for_date
from nutrition.services.quantities import resolve_factor

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]

#: Objectifs comparables aux totaux consommés.
GOAL_TO_NUTRIENT = {
    "daily_calories": "energy_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbohydrates_g",
    "fat_g": "fat_g",
    "fiber_g": "fiber_g",
}


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
        user = request.user

        meals = meal_types_service.meal_types_for(user, active_only=True).order_by(
            "sort_order", "id"
        )
        diary_day = DiaryDay.objects.filter(user=user, date=day).first()

        entries = (
            DiaryEntry.objects.filter(diary_day=diary_day)
            .select_related("meal_type")
            .order_by("consumed_at", "id")
            if diary_day
            else DiaryEntry.objects.none()
        )
        entries = list(entries)

        sections = []
        for meal in meals:
            meal_entries = [entry for entry in entries if entry.meal_type_id == meal.id]
            totals, incomplete = entries_service.sum_nutrition(meal_entries)
            sections.append(
                {
                    "meal_type": meal,
                    "entries": meal_entries,
                    "totals": totals,
                    "incomplete_nutrients": incomplete,
                }
            )

        totals, incomplete = entries_service.sum_nutrition(entries)
        goals = resolve_for_date(user, day)

        payload = {
            "date": day,
            "notes": diary_day.notes if diary_day else "",
            "goals": goals,
            "totals": totals,
            "incomplete_nutrients": incomplete,
            "remaining": _remaining(goals, totals),
            "meals": sections,
        }

        return Response(DiaryDaySerializer(payload).data)


def _remaining(goals: dict | None, totals: dict) -> dict | None:
    """Ce qu'il reste à consommer. `None` tant qu'aucun objectif n'est défini."""
    if not goals:
        return None

    remaining = {}
    for goal_field, nutrient in GOAL_TO_NUTRIENT.items():
        target = goals.get(goal_field)
        consumed = totals.get(nutrient)
        if target is None:
            remaining[goal_field] = None
            continue
        remaining[goal_field] = Decimal(target) - Decimal(consumed or 0)

    return remaining


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
