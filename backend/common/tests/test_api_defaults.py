"""Réglages DRF par défaut (spec 05 §12, spec 10 §5)."""

import pytest
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from accounts.models import UserStatus
from common.pagination import StandardPagination
from common.permissions import IsActiveAccount

factory = APIRequestFactory()


class _DefaultView(APIView):
    """Vue ne déclarant aucune permission : elle hérite des réglages globaux."""

    def get(self, request):
        return Response({"ok": True})


class _ActiveOnlyView(APIView):
    permission_classes = [IsActiveAccount]

    def get(self, request):
        return Response({"ok": True})


def test_une_vue_sans_permission_explicite_refuse_lanonyme():
    response = _DefaultView.as_view()(factory.get("/test/"))

    assert response.status_code == 401
    assert response.data["code"] == "not_authenticated"


@pytest.mark.django_db
def test_une_vue_sans_permission_explicite_accepte_un_utilisateur_authentifie(
    active_user,
):
    request = factory.get("/test/")
    force_authenticate(request, user=active_user)

    response = _DefaultView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status_value", "expected"),
    [(UserStatus.ACTIVE, 200), (UserStatus.PENDING, 403), (UserStatus.SUSPENDED, 403)],
)
def test_is_active_account_filtre_sur_le_statut(active_user, status_value, expected):
    active_user.status = status_value
    active_user.save()

    request = factory.get("/test/")
    force_authenticate(request, user=active_user)

    response = _ActiveOnlyView.as_view()(request)

    assert response.status_code == expected


def test_pagination_par_defaut():
    pagination = StandardPagination()

    assert pagination.page_size == 25
    assert pagination.page_query_param == "page"
    assert pagination.page_size_query_param == "limit"
    assert pagination.max_page_size == 100


def test_les_routes_sont_versionnees():
    assert reverse("api-v1:health") == "/api/v1/health/"
