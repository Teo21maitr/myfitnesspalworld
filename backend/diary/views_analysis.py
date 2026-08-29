"""Analyse et rapports (spec 04 §17-18).

Ces vues ne calculent rien : elles bornent une période, appellent les services
et sérialisent. La règle de l'étape vit dans
[`analysis`](diary/services/analysis.py) — les moyennes portent sur les
journées tenues — et une vue qui la ré-implémenterait finirait par la trahir.

Les exports sont **synchrones**. La spec 04 §17 ne demande l'asynchrone que
« si nécessaire », et un test mesure la durée sur quatre-vingt-dix jours : le
jour où il échouera, le socle de tâches de l'étape 12 est là.
"""

from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.dates import parse_iso_date, parse_period
from common.permissions import IsActiveAccount
from diary.serializers_analysis import NutrientAnalysisSerializer, ReportSerializer
from diary.services import analysis, reports

#: Longueur du résumé hebdomadaire, bornes comprises.
WEEK_DAYS = 7


class FoodAnalysisView(APIView):
    """`GET /analysis/food/?from=&to=&nutrient=` (spec 01 §21).

    D'où vient un nutriment sur la période. Les entrées qui ne le renseignent
    pas sont comptées à part : le total reste utile, mais annoncé partiel.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request: Request) -> Response:
        nutrient = request.query_params.get("nutrient") or "energy_kcal"
        if nutrient not in reports.CSV_NUTRIENTS:
            accepted = ", ".join(reports.CSV_NUTRIENTS)
            raise ValidationError(
                {"nutrient": f"Nutriment inconnu. Valeurs acceptées : {accepted}."}
            )

        start, end = _period(request.query_params.get("from"), request.query_params.get("to"))
        result = analysis.nutrient_sources(request.user, nutrient=nutrient, start=start, end=end)

        return Response(NutrientAnalysisSerializer(result).data)


class WeeklyAnalysisView(APIView):
    """`GET /analysis/weekly/?from=` (spec 01 §22).

    Sept jours à partir de `from`, ou la semaine en cours. C'est le rapport de
    période appliqué à une semaine : deux résumés distincts finiraient par
    afficher deux moyennes pour les mêmes journées.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request: Request) -> Response:
        start = parse_iso_date(request.query_params.get("from"), "from")
        if start is None:
            today = timezone.localdate()
            start = today - timedelta(days=today.weekday())

        report = reports.build(request.user, start, start + timedelta(days=WEEK_DAYS - 1))
        return Response(ReportSerializer(report).data)


class ReportSummaryView(APIView):
    """`GET /reports/summary/?from=&to=` (spec 04 §17)."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request: Request) -> Response:
        start, end = _period(request.query_params.get("from"), request.query_params.get("to"))
        return Response(ReportSerializer(reports.build(request.user, start, end)).data)


class ReportExportView(APIView):
    """Base des deux exports : même période, même rapport, deux formats."""

    permission_classes = [IsAuthenticated, IsActiveAccount]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reports"

    def build(self, request: Request) -> reports.Report:
        start, end = _period(request.data.get("from"), request.data.get("to"))
        return reports.build(request.user, start, end)

    def filename(self, report: reports.Report, extension: str) -> str:
        return f"myfitnesspalworld-{report.start:%Y%m%d}-{report.end:%Y%m%d}.{extension}"


class ReportCsvView(ReportExportView):
    """`POST /reports/csv/` (spec 04 §17)."""

    def post(self, request: Request) -> HttpResponse:
        report = self.build(request)
        # BOM : sans lui, Excel lit « protéines » en Latin-1 et affiche des
        # caractères de remplacement. Les autres tableurs l'ignorent.
        body = "﻿" + reports.to_csv(report)

        response = HttpResponse(body, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{self.filename(report, "csv")}"'
        return response


class ReportPdfView(ReportExportView):
    """`POST /reports/pdf/` (spec 04 §17)."""

    def post(self, request: Request) -> HttpResponse:
        report = self.build(request)

        response = HttpResponse(reports.to_pdf(report), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{self.filename(report, "pdf")}"'
        return response


def _period(raw_from, raw_to):
    return parse_period(
        raw_from,
        raw_to,
        default_days=reports.DEFAULT_REPORT_DAYS,
        max_days=reports.MAX_REPORT_DAYS,
    )
