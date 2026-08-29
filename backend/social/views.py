"""Vues des amitiés, des partages et de la consultation partagée.

Les routes de consultation sont **distinctes** de celles du propriétaire. Une
route qui servirait « mes données » ou « celles d'un autre » selon un paramètre
est la façon canonique de fabriquer un IDOR : il suffit d'oublier une
vérification sur un chemin. Ici, `/shared/` ne fait que lire, et chaque vue
commence par demander l'autorisation.
"""

from datetime import date as date_type

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User, UserStatus
from common.permissions import IsActiveAccount
from diary.serializers import DiaryDaySerializer
from diary.services import day as day_service
from diary.views import parse_date
from progress.models import WeightEntry
from progress.serializers import ChartSeriesSerializer, WeightEntrySerializer
from progress.services import charts
from progress.views import parse_period
from social.models import FriendRequest, FriendRequestStatus, ResourceType, SharePermission
from social.serializers import (
    FriendRequestCreateSerializer,
    FriendRequestSerializer,
    FriendSerializer,
    SharePermissionCreateSerializer,
    SharePermissionSerializer,
    UserSummarySerializer,
)
from social.services import friends as friends_service
from social.services import sharing

ACTIVE_USER = [IsAuthenticated, IsActiveAccount]


def raise_400(error: DjangoValidationError):
    """Convertit une erreur de service en réponse 400 cohérente."""
    raise ValidationError(getattr(error, "message_dict", None) or error.messages) from error


class UserSearchView(generics.ListAPIView):
    """`GET /users/search/?q=` — recherche partielle par nom d'utilisateur."""

    serializer_class = UserSummarySerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return friends_service.search_users(
            user=self.request.user, query=self.request.query_params.get("q", "")
        )


class FriendListView(generics.ListAPIView):
    """`GET /friends/`.

    Chaque ami porte `shares_diary` et `shares_progress` : sans eux,
    l'interface ne pourrait offrir « Son journal » qu'à l'aveugle, et le lien
    mènerait à un 404 chez qui n'a rien ouvert (spec 04 §12).
    """

    serializer_class = FriendSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return friends_service.friends_of(self.request.user)

    def get_serializer_context(self):
        # Une requête pour toute la page, plutôt qu'une par ami.
        return {**super().get_serializer_context(), "opened": sharing.opened_to(self.request.user)}


class FriendDetailView(APIView):
    """`DELETE /friends/{user_id}/` — retire un ami et révoque ses partages."""

    permission_classes = ACTIVE_USER

    def delete(self, request: Request, user_id: int) -> Response:
        other = User.objects.filter(pk=user_id).first()
        if other is None:
            raise NotFound("Compte introuvable.")

        try:
            friends_service.remove_friend(user=request.user, other=other)
        except DjangoValidationError as error:
            raise_400(error)

        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendRequestListCreateView(generics.ListCreateAPIView):
    """`GET|POST /friend-requests/` — les demandes en attente, reçues et envoyées."""

    serializer_class = FriendRequestSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return (
            FriendRequest.objects.filter(status=FriendRequestStatus.PENDING)
            .filter(Q(to_user=self.request.user) | Q(from_user=self.request.user))
            .select_related("from_user", "to_user")
        )

    def create(self, request, *args, **kwargs):
        serializer = FriendRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user = User.objects.get(pk=serializer.validated_data["to_user_id"])
        try:
            friend_request = friends_service.send_request(from_user=request.user, to_user=to_user)
        except DjangoValidationError as error:
            raise_400(error)

        return Response(
            FriendRequestSerializer(friend_request, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class FriendRequestActionView(APIView):
    """`POST /friend-requests/{id}/accept|reject/`."""

    permission_classes = ACTIVE_USER
    action = "accept"

    def post(self, request: Request, pk: int) -> Response:
        # Filtré sur le destinataire : une demande adressée à un autre compte
        # n'est pas atteignable, même en devinant son identifiant.
        friend_request = FriendRequest.objects.filter(pk=pk, to_user=request.user).first()
        if friend_request is None:
            raise NotFound("Demande introuvable.")

        handler = friends_service.accept if self.action == "accept" else friends_service.reject
        try:
            handler(request=friend_request, user=request.user)
        except DjangoValidationError as error:
            raise_400(error)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ShareListCreateView(generics.ListCreateAPIView):
    """`GET|POST /shares/` — ce que l'appelant partage."""

    serializer_class = SharePermissionSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        # Le sérialiseur rend les deux comptes : sans jointure, une requête par
        # ligne s'ajouterait à celle de la page.
        return SharePermission.objects.filter(owner=self.request.user).select_related(
            "owner", "target_user"
        )

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = SharePermissionSerializer(
            page, many=True, context={"request": request, "resource_names": sharing.describe(page)}
        )
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = SharePermissionCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        permission, _ = SharePermission.objects.get_or_create(
            owner=request.user,
            target_user=data["target"],
            resource_type=data["resource_type"],
            resource_id=data.get("resource_id"),
            defaults={"visibility_type": data["visibility"]},
        )

        if sharing.requires_resource_id(data["resource_type"]):
            # La fiche de la ressource doit annoncer ce qui vient d'être fait.
            sharing.sync_visibility(request.user, data["resource_type"], data["resource_id"])

        return Response(
            SharePermissionSerializer(
                permission,
                context={"request": request, "resource_names": sharing.describe([permission])},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ShareReceivedView(generics.ListAPIView):
    """`GET /shares/received/` — ce qu'on a partagé avec l'appelant."""

    serializer_class = SharePermissionSerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        # Un partage dont le propriétaire n'est plus actif ne compte pas
        # (spec 05 §2).
        return SharePermission.objects.filter(
            target_user=self.request.user, owner__status=UserStatus.ACTIVE
        ).select_related("owner", "target_user")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = SharePermissionSerializer(
            page, many=True, context={"request": request, "resource_names": sharing.describe(page)}
        )
        return self.get_paginated_response(serializer.data)


class ShareDetailView(generics.DestroyAPIView):
    """`DELETE /shares/{id}/` — révocation par le propriétaire."""

    permission_classes = ACTIVE_USER

    def get_queryset(self):
        return SharePermission.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance: SharePermission) -> None:
        resource_type, resource_id = instance.resource_type, instance.resource_id
        instance.delete()

        # Sans ce recalcul, la colonne continuerait d'annoncer « ouvert à
        # tous » alors que le partage vient d'être retiré.
        if sharing.requires_resource_id(resource_type):
            sharing.sync_visibility(self.request.user, resource_type, resource_id)


def shared_owner(request: Request, resource_type: str) -> User:
    """Propriétaire dont l'appelant peut lire cette ressource, sinon 404.

    Un 404 plutôt qu'un 403 : révéler qu'une ressource existe mais reste fermée
    renseignerait déjà sur les données d'autrui.

    L'identifiant est converti avant d'atteindre la base : passer une chaîne
    non numérique à `filter(pk=…)` faisait lever une `ValueError` que rien ne
    rattrapait, soit un 500 là où le contrat promet un 404.
    """
    raw = request.query_params.get("user_id")

    try:
        owner_id = int(raw) if raw else None
    except ValueError:
        owner_id = None

    owner = User.objects.filter(pk=owner_id).first() if owner_id is not None else None

    if owner is None or not sharing.can_read(request.user, owner, resource_type):
        raise NotFound("Contenu introuvable.")

    return owner


class SharedDiaryView(APIView):
    """`GET /shared/diary/?user_id=&date=` — journal d'un ami, en lecture seule."""

    permission_classes = ACTIVE_USER

    def get(self, request: Request) -> Response:
        owner = shared_owner(request, ResourceType.DIARY)
        day: date_type = parse_date(request.query_params.get("date"))

        # Le même service que le journal et le tableau de bord : les totaux ne
        # peuvent pas diverger selon qui regarde.
        return Response(DiaryDaySerializer(day_service.build_day(owner, day)).data)


class SharedProgressChartView(APIView):
    """`GET /shared/progress/charts/` — courbe d'un ami, en lecture seule."""

    permission_classes = ACTIVE_USER

    def get(self, request: Request) -> Response:
        owner = shared_owner(request, ResourceType.PROGRESS)

        metric = request.query_params.get("metric") or "weight"
        if metric not in charts.METRICS:
            raise NotFound("Métrique inconnue.")

        start, end = parse_period(request.query_params.get("from"), request.query_params.get("to"))
        return Response(ChartSeriesSerializer(charts.series(owner, metric, start, end)).data)


class SharedWeightView(generics.ListAPIView):
    """`GET /shared/progress/weight/?user_id=` — historique d'un ami."""

    serializer_class = WeightEntrySerializer
    permission_classes = ACTIVE_USER

    def get_queryset(self):
        owner = shared_owner(self.request, ResourceType.PROGRESS)
        return WeightEntry.objects.filter(user=owner)
