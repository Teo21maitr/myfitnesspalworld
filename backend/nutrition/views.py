"""Vues des objectifs nutritionnels et de l'onboarding (spec 04 §2)."""

from datetime import date

from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsActiveAccount
from nutrition.models import NutritionGoal
from nutrition.serializers import (
    CalorieCalculationSerializer,
    CalorieEstimateSerializer,
    DailyValuesSerializer,
    DayOverrideSerializer,
    NutritionGoalSerializer,
    NutritionGoalWriteSerializer,
    OnboardingSerializer,
)
from nutrition.services import goals as goals_service
from nutrition.services.calculation import (
    ESTIMATION_NOTICE,
    collect_warnings,
    estimate_from_profile_data,
)
from progress.models import WeightEntry


class AlreadyOnboarded(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Votre onboarding est déjà terminé."
    default_code = "onboarding_already_completed"


class CalorieCalculationView(APIView):
    """`POST /profile/goals/calculate/` — aperçu du calcul, rien n'est persisté.

    Le calcul vit uniquement côté serveur : le frontend affiche ce résultat
    mais ne le recalcule jamais lui-même (spec 05 §12).
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request: Request) -> Response:
        serializer = CalorieCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = estimate_from_profile_data(serializer.validated_data)
        return Response(CalorieEstimateSerializer(result).data)


class OnboardingView(APIView):
    """`POST /profile/onboarding/` — soumission complète et transactionnelle.

    Renseigne le profil, enregistre la première pesée et crée l'objectif
    initial. Soit tout réussit, soit rien n'est écrit.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request: Request) -> Response:
        profile = request.user.profile
        if profile.onboarding_completed:
            raise AlreadyOnboarded

        serializer = OnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        today = date.today()

        with transaction.atomic():
            profile.birth_date = data["birth_date"]
            profile.sex_for_calculation = data["sex_for_calculation"]
            profile.height_cm = data["height_cm"]
            profile.activity_level = data["activity_level"]
            profile.goal_type = data["goal_type"]
            profile.goal_rate_kg_per_week = data.get("goal_rate_kg_per_week")
            profile.target_weight_kg = data.get("target_weight_kg")
            profile.onboarding_completed = True
            profile.full_clean()
            profile.save()

            WeightEntry.objects.update_or_create(
                user=request.user,
                date=today,
                defaults={"weight_kg": data["weight_kg"]},
            )

            goal = goals_service.create_goal(
                request.user,
                start_date=today,
                daily_calories=data["daily_calories"],
                protein_g=data["protein_g"],
                carbs_g=data["carbs_g"],
                fat_g=data["fat_g"],
                fiber_g=data.get("fiber_g"),
                calories_source=data["calories_source"],
                macros_source=data["macros_source"],
            )

        warnings = collect_warnings(
            sex=data["sex_for_calculation"],
            daily_calories=data["daily_calories"],
            rate_kg_per_week=data.get("goal_rate_kg_per_week"),
            target_weight_kg=data.get("target_weight_kg"),
            height_cm=data["height_cm"],
        )

        return Response(
            {
                "goal": NutritionGoalSerializer(goal).data,
                "warnings": warnings,
                "notice": ESTIMATION_NOTICE,
            },
            status=status.HTTP_201_CREATED,
        )


class NutritionGoalListCreateView(generics.ListCreateAPIView):
    """`GET|POST /profile/goals/`.

    La liste est l'historique complet, du plus récent au plus ancien. Créer un
    objectif clôt le précédent : un changement n'est jamais rétroactif.
    """

    serializer_class = NutritionGoalSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return (
            NutritionGoal.objects.filter(user=self.request.user)
            .prefetch_related("day_overrides")
            .order_by("-start_date")
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = NutritionGoalWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        values = dict(serializer.validated_data)
        start_date = values.pop("start_date", None)

        goal = goals_service.create_goal(request.user, start_date=start_date, **values)
        return Response(NutritionGoalSerializer(goal).data, status=status.HTTP_201_CREATED)


class CurrentNutritionGoalView(APIView):
    """`GET /profile/goals/current/` — objectif applicable aujourd'hui."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request: Request) -> Response:
        goal = goals_service.current_goal(request.user)
        if goal is None:
            raise NotFound("Aucun objectif nutritionnel n’est défini.")

        resolved = goals_service.resolve_for_date(request.user, date.today())
        return Response(
            {
                "goal": NutritionGoalSerializer(goal).data,
                # Valeurs du jour, surcharge de jour de semaine appliquée.
                "today": DailyValuesSerializer(resolved).data,
            }
        )


class NutritionGoalDetailView(generics.RetrieveUpdateAPIView):
    """`GET|PATCH /profile/goals/{id}/`.

    Les objectifs passés restent modifiables par leur propriétaire, mais leur
    période ne l'est pas : `start_date` et `end_date` sont en lecture seule.
    """

    serializer_class = NutritionGoalSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return NutritionGoal.objects.filter(user=self.request.user).prefetch_related(
            "day_overrides"
        )


class DayOverrideView(APIView):
    """`PUT|DELETE /profile/goals/{id}/overrides/{weekday}/`.

    `weekday` suit la convention Python : 0 pour lundi, 6 pour dimanche.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_goal(self, request: Request, pk: int) -> NutritionGoal:
        try:
            return NutritionGoal.objects.get(pk=pk, user=request.user)
        except NutritionGoal.DoesNotExist as exc:
            raise NotFound("Objectif introuvable.") from exc

    def put(self, request: Request, pk: int, weekday: int) -> Response:
        goal = self.get_goal(request, pk)

        serializer = DayOverrideSerializer(data={**request.data, "weekday": weekday})
        serializer.is_valid(raise_exception=True)

        values = dict(serializer.validated_data)
        values.pop("weekday", None)
        override = goals_service.set_day_override(goal, weekday, **values)

        return Response(DayOverrideSerializer(override).data)

    def delete(self, request: Request, pk: int, weekday: int) -> Response:
        goal = self.get_goal(request, pk)
        goal.day_overrides.filter(weekday=weekday).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
