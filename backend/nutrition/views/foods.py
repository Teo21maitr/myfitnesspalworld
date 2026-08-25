"""Vues du référentiel d'aliments (spec 04 §3).

Les querysets sont filtrés par visibilité en base : aucun aliment invisible ne
peut être atteint, même en devinant son identifiant (spec 05 §12).
"""

from django.db.models import Prefetch, Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from nutrition.models import Food, FoodPortion, FoodSource, UserFoodFavorite
from nutrition.serializers import (
    FoodDetailSerializer,
    FoodListSerializer,
    FoodPortionSerializer,
    FoodWriteSerializer,
)
from nutrition.services import search as search_service

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]


def visible_foods(request: Request):
    """Aliments consultables, avec leurs portions et leur nutrition."""
    return (
        Food.objects.visible_to(request.user)
        .select_related("nutrition")
        .prefetch_related(
            Prefetch(
                "portions",
                # Portions officielles et portions personnelles de l'appelant.
                queryset=FoodPortion.objects.filter(Q(owner__isnull=True) | Q(owner=request.user)),
            )
        )
    )


class FoodSearchView(generics.ListAPIView):
    """`GET /foods/search/?q=` — recherche classée (spec 01 §7)."""

    serializer_class = FoodListSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return search_service.search_foods(
            self.request.user, self.request.query_params.get("q", "")
        )


class FoodRecentView(generics.ListAPIView):
    """`GET /foods/recent/` — 50 derniers aliments distincts utilisés."""

    serializer_class = FoodListSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return search_service.annotate_personal_signals(
            search_service.recent_foods(self.request.user), self.request.user
        )


class FoodFrequentView(generics.ListAPIView):
    """`GET /foods/frequent/` — aliments les plus utilisés."""

    serializer_class = FoodListSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return search_service.annotate_personal_signals(
            search_service.frequent_foods(self.request.user), self.request.user
        )


class FoodFavoritesView(generics.ListAPIView):
    """`GET /foods/favorites/` — aliments marqués d'une étoile."""

    serializer_class = FoodListSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return search_service.annotate_personal_signals(
            search_service.favorite_foods(self.request.user), self.request.user
        )


class FoodListCreateView(generics.ListCreateAPIView):
    """`GET|POST /foods/` — aliments personnels de l'utilisateur."""

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return FoodWriteSerializer if self.request.method == "POST" else FoodListSerializer

    def get_queryset(self):
        return search_service.annotate_personal_signals(
            Food.objects.editable_by(self.request.user).select_related("nutrition"),
            self.request.user,
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        food = serializer.save()

        return Response(
            FoodDetailSerializer(food, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class FoodDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /foods/{id}/`.

    Un aliment global ou celui d'un autre utilisateur est consultable mais
    jamais modifiable : il faut en créer sa propre version (spec 01 §8).
    """

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return (
            FoodWriteSerializer if self.request.method in ("PUT", "PATCH") else FoodDetailSerializer
        )

    def get_queryset(self):
        return search_service.annotate_personal_signals(
            visible_foods(self.request), self.request.user
        )

    def _ensure_editable(self, food: Food) -> None:
        if food.source != FoodSource.USER or food.owner_id != self.request.user.id:
            raise PermissionDenied(
                "Cet aliment ne vous appartient pas. Dupliquez-le pour en créer votre version."
            )

    def update(self, request: Request, *args, **kwargs) -> Response:
        food = self.get_object()
        self._ensure_editable(food)

        serializer = self.get_serializer(
            food, data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(FoodDetailSerializer(food, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance: Food) -> None:
        self._ensure_editable(instance)
        # Suppression douce : les entrées de journal déjà créées conservent
        # leur snapshot, mais l'aliment disparaît des recherches (spec 05 §11).
        instance.is_active = False
        instance.deleted_at = instance.updated_at
        instance.save(update_fields=["is_active", "deleted_at", "updated_at"])


class FoodFavoriteView(APIView):
    """`POST|DELETE /foods/{id}/favorite/` — étoile manuelle."""

    permission_classes = ACTIVE_USER

    def get_food(self, request: Request, pk: int) -> Food:
        return generics.get_object_or_404(Food.objects.visible_to(request.user), pk=pk)

    def post(self, request: Request, pk: int) -> Response:
        food = self.get_food(request, pk)
        UserFoodFavorite.objects.get_or_create(user=request.user, food=food)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, pk: int) -> Response:
        food = self.get_food(request, pk)
        UserFoodFavorite.objects.filter(user=request.user, food=food).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FoodPortionListCreateView(generics.ListCreateAPIView):
    """`GET|POST /foods/{id}/portions/`.

    Une portion ajoutée sur un aliment global reste privée à son créateur
    (spec 01 §9).
    """

    serializer_class = FoodPortionSerializer
    permission_classes = ACTIVE_USER

    def get_food(self) -> Food:
        return generics.get_object_or_404(
            Food.objects.visible_to(self.request.user), pk=self.kwargs["pk"]
        )

    def get_queryset(self):
        return self.get_food().portions.filter(Q(owner__isnull=True) | Q(owner=self.request.user))

    def perform_create(self, serializer) -> None:
        serializer.save(food=self.get_food(), owner=self.request.user)


class FoodPortionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /foods/{id}/portions/{portion_id}/`."""

    serializer_class = FoodPortionSerializer
    permission_classes = ACTIVE_USER
    lookup_url_kwarg = "portion_id"

    def get_queryset(self):
        # Seules ses propres portions sont modifiables.
        return FoodPortion.objects.filter(food_id=self.kwargs["pk"], owner=self.request.user)
