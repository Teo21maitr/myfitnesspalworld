"""Vues de la liste de courses (spec 04 §11).

Une liste reçue se lit ; elle ne se coche pas. Les écritures passent toutes par
`editable_by()`, les lectures par `visible_to()` (spec 05 §7).
"""

from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from planning.models import ItemSource, ShoppingList, ShoppingListItem, ShoppingVisibility
from planning.serializers import (
    GenerateSerializer,
    ShoppingListItemSerializer,
    ShoppingListItemWriteSerializer,
    ShoppingListSerializer,
    ShoppingListWriteSerializer,
)
from planning.services import shopping
from social.models import ResourceType
from social.services.sharing import revoke_resource

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]


def owned_list(request: Request, pk: int) -> ShoppingList:
    """Liste appartenant à l'appelant, sinon 404."""
    shopping_list = ShoppingList.objects.editable_by(request.user).filter(pk=pk).first()
    if shopping_list is None:
        raise NotFound("Liste introuvable.")
    return shopping_list


class ShoppingListListCreateView(generics.ListCreateAPIView):
    """`GET|POST /shopping-lists/`."""

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return (
            ShoppingListWriteSerializer if self.request.method == "POST" else ShoppingListSerializer
        )

    def get_queryset(self):
        return ShoppingList.objects.visible_to(self.request.user).prefetch_related("items")

    def create(self, request, *args, **kwargs):
        serializer = ShoppingListWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shopping_list = serializer.save(owner=request.user)

        return Response(
            ShoppingListSerializer(shopping_list, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ShoppingListDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /shopping-lists/{id}/`.

    La suppression est franche : une liste est un brouillon, rien ne la
    référence (spec 01 §16).
    """

    permission_classes = ACTIVE_USER

    def get_serializer_class(self):
        return (
            ShoppingListWriteSerializer
            if self.request.method in ("PATCH", "PUT")
            else ShoppingListSerializer
        )

    def get_queryset(self):
        base = (
            ShoppingList.objects.visible_to(self.request.user)
            if self.request.method in ("GET", "HEAD")
            else ShoppingList.objects.editable_by(self.request.user)
        )
        return base.prefetch_related("items")

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ShoppingListWriteSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        shopping_list = serializer.save()

        if shopping_list.visibility == ShoppingVisibility.PRIVATE:
            # Déclarer « privé » referme les partages déjà accordés.
            revoke_resource(ResourceType.SHOPPING_LIST, shopping_list.pk)

        return Response(ShoppingListSerializer(shopping_list, context={"request": request}).data)


class ShoppingListGenerateView(APIView):
    """`POST /shopping-lists/generate/` — depuis des recettes ou des journées."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request) -> Response:
        serializer = GenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "shopping_list_id" in data:
            shopping_list = owned_list(request, data["shopping_list_id"])
        else:
            shopping_list = ShoppingList.objects.create(
                owner=request.user, name=data.get("name") or "Mes courses"
            )

        lines = shopping.lines_from_recipes(request.user, data.get("recipe_ids", []))
        lines += shopping.lines_from_days(request.user, data.get("dates", []))
        shopping.add_lines(shopping_list, lines)

        shopping_list.refresh_from_db()
        return Response(
            ShoppingListSerializer(shopping_list, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ShoppingListItemCreateView(APIView):
    """`POST /shopping-lists/{id}/items/` — ajout manuel."""

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        shopping_list = owned_list(request, pk)

        serializer = ShoppingListItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        item = ShoppingListItem.objects.create(
            shopping_list=shopping_list,
            name=data["name"],
            quantity=data.get("quantity"),
            unit_label=data.get("unit_label") or None,
            source_type=ItemSource.MANUAL,
            sort_order=shopping_list.items.count(),
        )

        return Response(ShoppingListItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ShoppingListItemDetailView(generics.UpdateAPIView, generics.DestroyAPIView):
    """`PATCH|DELETE /shopping-lists/{id}/items/{item_id}/`.

    Cocher est une écriture : une liste reçue ne se coche pas.
    """

    serializer_class = ShoppingListItemSerializer
    permission_classes = ACTIVE_USER
    lookup_url_kwarg = "item_id"

    def get_queryset(self):
        return ShoppingListItem.objects.filter(
            shopping_list__pk=self.kwargs["pk"],
            shopping_list__owner=self.request.user,
        )
