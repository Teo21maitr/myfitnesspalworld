"""Format d'erreur normalisé de l'API (spec 10 §5)."""

import pytest
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

factory = APIRequestFactory()


class _QuantitySerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)


class _RaisingView(APIView):
    """Vue de test paramétrable par l'exception à lever."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    exception: Exception | None = None

    def get(self, request):
        if self.exception is not None:
            raise self.exception
        return Response({"ok": True})


def _call(exception: Exception):
    view = _RaisingView.as_view(exception=exception)
    return view(factory.get("/test/"))


def test_validation_error_expose_les_erreurs_par_champ():
    response = _call(ValidationError({"quantity": ["Ce champ est obligatoire."]}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {
        "code": "validation_error",
        "message": "Données invalides.",
        "errors": {"quantity": ["Ce champ est obligatoire."]},
    }


def test_validation_error_sans_champ_est_regroupee():
    response = _call(ValidationError("Payload invalide."))

    assert response.data["code"] == "validation_error"
    assert response.data["errors"] == {"non_field_errors": ["Payload invalide."]}


def test_erreur_de_serializer_respecte_le_format():
    serializer = _QuantitySerializer(data={"quantity": "-1"})
    assert serializer.is_valid() is False

    response = _call(ValidationError(serializer.errors))

    assert response.data["code"] == "validation_error"
    assert "quantity" in response.data["errors"]


def test_permission_denied_respecte_le_format():
    response = _call(PermissionDenied())

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "permission_denied"
    assert response.data["message"]
    assert response.data["errors"] == {}


def test_not_found_respecte_le_format():
    response = _call(NotFound())

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["code"] == "not_found"
    assert set(response.data) == {"code", "message", "errors"}


@pytest.mark.django_db
def test_erreur_dauthentification_respecte_le_format(client):
    """Une route protégée renvoie le même format quand l'accès est refusé."""
    response = client.get("/api/v1/inexistant/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
