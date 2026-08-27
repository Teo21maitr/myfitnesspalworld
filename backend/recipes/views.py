"""Vues des recettes et des repas enregistrés (spec 04 §6 et §7).

Tous les querysets sont filtrés par visibilité, et l'écriture par propriété :
aucune ressource d'un autre compte n'est atteignable, même en devinant son
identifiant (spec 05 §12).
"""

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from diary.models import MealType
from diary.serializers import DiaryEntrySerializer
from diary.services.entries import create_recipe_entry
from recipes.models import Recipe, SavedMeal
from recipes.serializers import (
    AddRecipeToDiarySerializer,
    AddSavedMealToDiarySerializer,
    RecipeDetailSerializer,
    RecipeListSerializer,
    RecipeWriteSerializer,
    SavedMealSerializer,
    SavedMealWriteSerializer,
)
from recipes.services import library
from recipes.services import nutrition as nutrition_service

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]


def resolve_meal_type(user, meal_type_id: int) -> MealType:
    meal_type = MealType.objects.filter(pk=meal_type_id, user=user).first()
    if meal_type is None:
        raise NotFound("Repas introuvable.")
    return meal_type


def fresh(recipe: Recipe) -> Recipe:
    """Recette dont le cache nutritionnel est à jour avant sérialisation."""
    nutrition_service.ensure_fresh(recipe)
    recipe.refresh_from_db()
    return recipe


class RecipeListCreateView(generics.ListCreateAPIView):
    """`GET|POST /recipes/`."""

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return RecipeWriteSerializer if self.request.method == "POST" else RecipeListSerializer

    def get_queryset(self):
        queryset = (
            Recipe.objects.visible_to(self.request.user)
            .select_related("nutrition")
            .prefetch_related("ingredients")
        )
        # Un agrégat par recette ferait vingt-cinq requêtes sur une page.
        # L'annotation introduit un GROUP BY, qui neutralise le tri implicite
        # du modèle : il faut le redire pour que la pagination reste stable.
        return nutrition_service.annotate_freshness(queryset).order_by("name", "id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        for recipe in page:
            nutrition_service.ensure_fresh(recipe)

        serializer = RecipeListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = RecipeWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()

        return Response(
            RecipeDetailSerializer(recipe, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RecipeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /recipes/{id}/`.

    `DELETE` est une suppression douce : les entrées de journal la référencent
    et l'historique doit rester valide (spec 01 §14).
    """

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return (
            RecipeWriteSerializer
            if self.request.method in ("PATCH", "PUT")
            else RecipeDetailSerializer
        )

    def get_queryset(self):
        base = (
            Recipe.objects.editable_by(self.request.user)
            if self.request.method not in ("GET", "HEAD")
            else Recipe.objects.visible_to(self.request.user)
        )
        return nutrition_service.annotate_freshness(
            base.select_related("nutrition").prefetch_related("ingredients")
        )

    def retrieve(self, request, *args, **kwargs):
        recipe = fresh(self.get_object())
        return Response(RecipeDetailSerializer(recipe, context={"request": request}).data)

    def update(self, request, *args, **kwargs):
        serializer = RecipeWriteSerializer(
            self.get_object(), data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()

        return Response(RecipeDetailSerializer(recipe, context={"request": request}).data)

    def perform_destroy(self, instance: Recipe) -> None:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at"])


class RecipeDuplicateView(APIView):
    """`POST /recipes/{id}/duplicate/` — copie indépendante (spec 01 §18)."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        recipe = Recipe.objects.visible_to(request.user).filter(pk=pk).first()
        if recipe is None:
            raise NotFound("Recette introuvable.")

        copy = library.duplicate_recipe(user=request.user, recipe=recipe)
        return Response(
            RecipeDetailSerializer(copy, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RecipeFavoriteView(APIView):
    """`POST|DELETE /recipes/{id}/favorite/`."""

    permission_classes = ACTIVE_USER

    def _recipe(self, request: Request, pk: int) -> Recipe:
        recipe = Recipe.objects.editable_by(request.user).filter(pk=pk).first()
        if recipe is None:
            raise NotFound("Recette introuvable.")
        return recipe

    def post(self, request: Request, pk: int) -> Response:
        recipe = self._recipe(request, pk)
        recipe.is_favorite = True
        recipe.save(update_fields=["is_favorite", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, pk: int) -> Response:
        recipe = self._recipe(request, pk)
        recipe.is_favorite = False
        recipe.save(update_fields=["is_favorite", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeAddToDiaryView(APIView):
    """`POST /recipes/{id}/add-to-diary/` — N portions (spec 04 §6)."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        recipe = Recipe.objects.visible_to(request.user).filter(pk=pk).first()
        if recipe is None:
            raise NotFound("Recette introuvable.")

        serializer = AddRecipeToDiarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        entry = create_recipe_entry(
            user=request.user,
            recipe=recipe,
            day=data["date"],
            meal_type=resolve_meal_type(request.user, data["meal_type_id"]),
            servings=data["servings"],
            consumed_at=data.get("consumed_at") or timezone.now(),
            note=data["note"],
        )

        return Response(DiaryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class SavedMealListCreateView(generics.ListCreateAPIView):
    """`GET|POST /saved-meals/`."""

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return SavedMealWriteSerializer if self.request.method == "POST" else SavedMealSerializer

    def get_queryset(self):
        return SavedMeal.objects.visible_to(self.request.user).prefetch_related("items")

    def create(self, request, *args, **kwargs):
        serializer = SavedMealWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        saved_meal = serializer.save()

        return Response(
            SavedMealSerializer(saved_meal, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SavedMealDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /saved-meals/{id}/`."""

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return (
            SavedMealWriteSerializer
            if self.request.method in ("PATCH", "PUT")
            else SavedMealSerializer
        )

    def get_queryset(self):
        base = (
            SavedMeal.objects.editable_by(self.request.user)
            if self.request.method not in ("GET", "HEAD")
            else SavedMeal.objects.visible_to(self.request.user)
        )
        return base.prefetch_related("items")

    def update(self, request, *args, **kwargs):
        serializer = SavedMealWriteSerializer(
            self.get_object(), data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        saved_meal = serializer.save()

        return Response(SavedMealSerializer(saved_meal, context={"request": request}).data)

    def perform_destroy(self, instance: SavedMeal) -> None:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at"])


class SavedMealDuplicateView(APIView):
    """`POST /saved-meals/{id}/duplicate/`."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        saved_meal = SavedMeal.objects.visible_to(request.user).filter(pk=pk).first()
        if saved_meal is None:
            raise NotFound("Repas introuvable.")

        copy = library.duplicate_saved_meal(user=request.user, saved_meal=saved_meal)
        return Response(
            SavedMealSerializer(copy, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SavedMealAddToDiaryView(APIView):
    """`POST /saved-meals/{id}/add-to-diary/` — déplie en entrées normales."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        saved_meal = SavedMeal.objects.visible_to(request.user).filter(pk=pk).first()
        if saved_meal is None:
            raise NotFound("Repas introuvable.")

        serializer = AddSavedMealToDiarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        entries, skipped = library.add_saved_meal_to_diary(
            user=request.user,
            saved_meal=saved_meal,
            day=data["date"],
            meal_type=resolve_meal_type(request.user, data["meal_type_id"]),
            consumed_at=data.get("consumed_at") or timezone.now(),
        )

        return Response(
            {
                "entries": DiaryEntrySerializer(entries, many=True).data,
                # Les éléments dont la source a disparu sont nommés plutôt
                # qu'omis en silence.
                "skipped": skipped,
            },
            status=status.HTTP_201_CREATED,
        )
