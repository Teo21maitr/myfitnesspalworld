"""Endpoints adossés à Open Food Facts (spec 04 §3, spec 11 §3 et §4).

Deux garde-fous encadrent chaque appel sortant : le throttling DRF, qui limite
un utilisateur, et le budget global de `common.rate_limit`, qui limite
l'application entière — Open Food Facts comptant par adresse IP, tous les
comptes partagent le même quota.
"""

import re

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from nutrition import tasks
from nutrition.exceptions import ExternalSourceUnavailable, InvalidBarcode, ProductNotFound
from nutrition.models import Food, FoodSource
from nutrition.serializers import ExternalFoodCandidateSerializer, FoodDetailSerializer
from nutrition.services import off as off_service
from nutrition.services import off_client
from nutrition.services.search import MINIMUM_QUERY_LENGTH

from .foods import ACTIVE_USER, visible_foods

#: Une liste courte. Une recherche de marque renvoie souvent des dizaines
#: de fiches quasi identiques : au-delà d'une dizaine, elles ne rendent
#: plus le choix plus facile, seulement plus long.
EXTERNAL_SEARCH_LIMIT = 10

#: Codes acceptés : uniquement des chiffres, 8 à 24 positions.
#:
#: Les standards du commerce s'arrêtent à 14 chiffres (EAN-8, UPC, EAN-13,
#: ITF-14), mais Open Food Facts référence aussi des codes plus longs — on en
#: rencontre de 18 chiffres dans ses résultats de recherche. Se limiter aux
#: standards rendrait ces produits impossibles à ouvrir. La validation garde
#: son rôle : écarter les saisies erronées avant de dépenser du quota.
BARCODE_PATTERN = re.compile(r"^\d{8,24}$")


def clean_barcode(raw: str) -> str:
    """Valide un code-barres avant toute dépense de quota."""
    barcode = (raw or "").strip()
    if not BARCODE_PATTERN.match(barcode):
        raise InvalidBarcode()
    return barcode


class BarcodeLookupView(APIView):
    """`GET /barcodes/{barcode}/` — résout un code-barres (spec 11 §4).

    Ordre de résolution : l'aliment personnel de l'utilisateur portant ce code,
    puis le cache local des produits déjà rapatriés, puis seulement la source
    externe. Un produit inconnu répond 404, ce qui déclenche la création
    manuelle côté interface.
    """

    permission_classes = ACTIVE_USER
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "off_barcode"

    def get(self, request: Request, barcode: str) -> Response:
        barcode = clean_barcode(barcode)
        base = visible_foods(request)

        # 1. Un aliment personnel prime : l'utilisateur a délibérément créé sa
        # propre version de ce produit.
        own = base.filter(owner=request.user, source=FoodSource.USER, barcode=barcode).first()
        if own is not None:
            return Response(FoodDetailSerializer(own, context={"request": request}).data)

        # 2. Produit déjà rapatrié : servi immédiatement, et rafraîchi en tâche
        # de fond s'il a vieilli.
        cached = base.filter(source=FoodSource.OFF, external_id=barcode).first()
        if cached is not None:
            tasks.schedule_refresh(cached)
            return Response(FoodDetailSerializer(cached, context={"request": request}).data)

        # 3. Appel à la source.
        try:
            product = off_client.fetch_product(barcode)
        except off_client.ProductNotFound as error:
            raise ProductNotFound() from error
        except off_client.OpenFoodFactsUnavailable as error:
            raise ExternalSourceUnavailable() from error

        try:
            food = off_service.upsert_product(product)
        except off_service.UnusableProduct as error:
            # Fiche sans nom exploitable : pour l'utilisateur, c'est un produit
            # inconnu de plus.
            raise ProductNotFound() from error

        food = visible_foods(request).get(pk=food.pk)
        return Response(
            FoodDetailSerializer(food, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class ExternalFoodSearchView(APIView):
    """`GET /foods/external-search/?q=` — recherche élargie à Open Food Facts.

    Jamais déclenchée à la frappe : l'utilisateur la demande explicitement
    (spec 11 §5). Les résultats ne sont pas persistés — seul le produit
    finalement choisi l'est, via `GET /barcodes/{code}/`.
    """

    permission_classes = ACTIVE_USER
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "off_search"

    def get(self, request: Request) -> Response:
        query = (request.query_params.get("q") or "").strip()
        if len(query) < MINIMUM_QUERY_LENGTH:
            return Response({"results": []})

        try:
            candidates = off_client.search_products(query, limit=EXTERNAL_SEARCH_LIMIT)
        except off_client.OpenFoodFactsUnavailable as error:
            raise ExternalSourceUnavailable() from error

        # Les produits déjà en base sont signalés : l'interface peut ouvrir
        # leur fiche sans redépenser de quota.
        known = dict(
            Food.objects.filter(
                source=FoodSource.OFF,
                external_id__in=[candidate.code for candidate in candidates],
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("external_id", "id")
        )

        # Un candidat dont le code ne serait pas résolvable ne doit pas être
        # proposé : le clic échouerait.
        results = [
            {
                "code": candidate.code,
                "name": candidate.name,
                "brand": candidate.brand,
                "food_id": known.get(candidate.code),
            }
            for candidate in candidates
            if BARCODE_PATTERN.match(candidate.code)
        ]

        return Response({"results": ExternalFoodCandidateSerializer(results, many=True).data})
