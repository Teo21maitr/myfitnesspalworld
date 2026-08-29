"""Vues du planning et de la liste de courses (spec 04 §8, §11).

Une liste reçue se lit ; elle ne se coche pas. Les écritures passent toutes par
`editable_by()`, les lectures par `visible_to()` (spec 05 §7).

Un planning n'est jamais partagé : il appartient à son auteur, et la 404 d'un
plan qui n'est pas le sien évite de renseigner sur l'activité d'autrui.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ai.exceptions import AIUnavailable
from ai.services import gate
from ai.tasks import generate_meal_plan_task, regenerate_plan_meal_task
from ai.views import RESULT_RETENTION_HOURS
from common.models import AsyncTask, TaskType
from common.permissions import IsActiveAccount
from common.serializers import AsyncTaskSerializer
from diary.serializers import DiaryEntrySerializer
from planning.models import (
    ItemSource,
    MealPlan,
    ShoppingList,
    ShoppingListItem,
    ShoppingVisibility,
)
from planning.serializers import (
    GeneratePlanSerializer,
    GenerateSerializer,
    MealPlanListSerializer,
    MealPlanSerializer,
    MealPlanWriteSerializer,
    RegenerateMealSerializer,
    ShoppingListItemSerializer,
    ShoppingListItemWriteSerializer,
    ShoppingListSerializer,
    ShoppingListWriteSerializer,
)
from planning.services import plans, shopping
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
        if data.get("meal_plan_id"):
            lines += shopping.lines_from_meal_plan(request.user, data["meal_plan_id"])
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


# -----------------------------------------------------------------------------
# Planning (spec 04 §8)
# -----------------------------------------------------------------------------


def owned_plan(request: Request, pk: int) -> MealPlan:
    """Plan appartenant à l'appelant, sinon 404.

    404 et non 403 : dire qu'un plan existe mais reste fermé renseignerait déjà
    sur les données d'autrui (spec 04 §13 bis).
    """
    plan = MealPlan.objects.filter(pk=pk, owner=request.user).first()
    if plan is None:
        raise NotFound("Planning introuvable.")
    return plan


class MealPlanListCreateView(generics.ListCreateAPIView):
    """`GET|POST /meal-plans/`.

    `POST` enregistre une proposition relue par l'utilisateur — c'est ici, et
    seulement ici, que les recettes inventées deviennent de vraies recettes
    (spec 07 §8).
    """

    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return MealPlan.objects.filter(owner=self.request.user).prefetch_related("days")

    def get_serializer_class(self):
        return MealPlanWriteSerializer if self.request.method == "POST" else MealPlanListSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = MealPlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan, skipped = plans.create_plan(user=request.user, payload=serializer.validated_data)

        body = MealPlanSerializer(plan, context={"request": request}).data
        # Une recette dont aucun ingrédient ne se retrouve est nommée plutôt
        # qu'enregistrée incomplète.
        body["skipped_recipes"] = skipped
        return Response(body, status=status.HTTP_201_CREATED)


class MealPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """`GET|PATCH|DELETE /meal-plans/{id}/`.

    Suppression franche : un plan est une intention, pas un historique, et le
    journal qu'on en a tiré lui survit sous forme d'entrées indépendantes.
    """

    permission_classes = ACTIVE_USER
    serializer_class = MealPlanSerializer

    def get_queryset(self):
        return MealPlan.objects.filter(owner=self.request.user).prefetch_related(
            "days__entries__meal_type",
            "days__entries__food__nutrition",
            "days__entries__food__portions",
            "days__entries__recipe__nutrition",
        )

    def get_serializer_class(self):
        return MealPlanWriteSerializer if self.request.method == "PATCH" else MealPlanSerializer

    def update(self, request: Request, *args, **kwargs) -> Response:
        # Seul le nom et les notes se modifient ici : le contenu se corrige
        # entrée par entrée, ou se régénère.
        plan = self.get_object()
        for field in ("name", "notes"):
            if field in request.data:
                setattr(plan, field, request.data[field])
        plan.save(update_fields=["name", "notes", "updated_at"])
        return Response(MealPlanSerializer(plan, context={"request": request}).data)


class MealPlanGenerateView(APIView):
    """`POST /meal-plans/generate/` — compose une proposition (spec 04 §8).

    Répond 202 : la composition dure plusieurs dizaines de secondes — une
    journée par appel au modèle, parfois trois quand elle sort des tolérances.
    Rien n'est persisté : c'est `POST /meal-plans/` qui écrit.
    """

    permission_classes = ACTIVE_USER
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request: Request) -> Response:
        if not gate.is_enabled():
            raise AIUnavailable()

        serializer = GeneratePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        task = AsyncTask.objects.create(
            user=request.user,
            task_type=TaskType.MEAL_PLANNER,
            expires_at=timezone.now() + timedelta(hours=RESULT_RETENTION_HOURS),
        )

        generate_meal_plan_task.delay(
            str(task.pk),
            {
                **data,
                "start_date": data["start_date"].isoformat(),
                "end_date": data["end_date"].isoformat(),
            },
        )

        task.refresh_from_db()
        return Response(AsyncTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)


class MealPlanAddToDiaryView(APIView):
    """`POST /meal-plans/{id}/add-to-diary/`.

    **N'écrase jamais** (spec 01 §15). Un repas déjà rempli est nommé et
    l'ajout attend confirmation ; confirmé, les entrées s'ajoutent par-dessus,
    elles ne remplacent rien.
    """

    permission_classes = ACTIVE_USER

    def post(self, request: Request, pk: int) -> Response:
        plan = owned_plan(request, pk)
        conflicts = plans.filled_meals(request.user, plan)

        if conflicts and not request.data.get("confirm"):
            return Response({"entries": [], "skipped": [], "conflicts": conflicts})

        entries, skipped = plans.add_plan_to_diary(user=request.user, plan=plan)

        return Response(
            {
                "entries": DiaryEntrySerializer(entries, many=True).data,
                "skipped": skipped,
                "conflicts": conflicts,
            },
            status=status.HTTP_201_CREATED,
        )


class MealPlanRegenerateMealView(APIView):
    """`POST /meal-plans/{id}/regenerate-entry/` — recompose un seul repas.

    Ne puise que dans l'existant : une recette inventée ne s'enregistre qu'à
    l'acceptation d'un plan (spec 07 §8), et la régénération écrit directement
    dans le plan. Le journal, lui, n'est jamais touché sans confirmation.
    """

    permission_classes = ACTIVE_USER
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request: Request, pk: int) -> Response:
        if not gate.is_enabled():
            raise AIUnavailable()

        plan = owned_plan(request, pk)
        serializer = RegenerateMealSerializer(data=request.data, context={"plan": plan})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        task = AsyncTask.objects.create(
            user=request.user,
            task_type=TaskType.MEAL_PLANNER,
            expires_at=timezone.now() + timedelta(hours=RESULT_RETENTION_HOURS),
        )

        regenerate_plan_meal_task.delay(str(task.pk), plan.pk, data["day_id"], data["meal_type_id"])

        task.refresh_from_db()
        return Response(AsyncTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)
