"""Rapports de période : résumé, CSV et PDF (spec 01 §22, spec 04 §17).

Un rapport **ne calcule rien de neuf**. Il assemble ce que les services
existants savent déjà produire — les totaux du journal, les objectifs de chaque
date, la série de poids et sa moyenne mobile — pour qu'un même intervalle ne
puisse pas raconter deux histoires selon l'écran qui l'affiche.

Il hérite donc de leurs règles, et la principale est celle de l'étape : les
moyennes portent sur les **journées tenues**. Un rapport qui diviserait par la
longueur du calendrier récompenserait l'oubli de journaliser.

Les valeurs viennent des snapshots des entrées : corriger une fiche aujourd'hui
ne réécrit pas le rapport d'août (spec 01 §6).
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal

from accounts.models import User
from diary.services import analysis
from nutrition.models.nutrients import NUTRIENT_FIELDS, nutrient_label
from nutrition.services.goals import resolve_for_date
from progress.services import charts

#: Le CSV emporte **tous** les nutriments : c'est ce qu'on attend d'un export,
#: et une colonne vide dit « non renseigné » sans ambiguïté.
CSV_NUTRIENTS: tuple[str, ...] = NUTRIENT_FIELDS

#: Ce que le résumé et le PDF mettent en avant (spec 01 §22).
SUMMARY_NUTRIENTS: tuple[str, ...] = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
    "fiber_g",
)

#: Même plafond que les courbes de progression : deux ans.
MAX_REPORT_DAYS = charts.MAX_PERIOD_DAYS

#: Période retenue quand l'appelant n'en précise aucune.
DEFAULT_REPORT_DAYS = 30


@dataclass
class DayRow:
    """Une journée tenue, avec ce qu'elle visait et ce qu'elle a pesé."""

    date: date_type
    totals: dict[str, Decimal | None]
    incomplete_nutrients: list[str]
    entries: int
    target_calories: Decimal | None = None
    weight_kg: Decimal | None = None


@dataclass
class Report:
    start: date_type
    end: date_type
    days: list[DayRow] = field(default_factory=list)
    averages: dict[str, Decimal | None] = field(default_factory=dict)
    adherence: dict = field(default_factory=dict)
    weight: dict = field(default_factory=dict)
    top_foods: list[analysis.Source] = field(default_factory=list)

    @property
    def logged_days(self) -> int:
        return len(self.days)

    @property
    def calendar_days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def weight_change(self) -> Decimal | None:
        """Variation entre la première et la dernière pesée de la période.

        `None` sous deux pesées : un point unique ne dit rien d'une variation.
        """
        points = self.weight.get("points") or []
        if len(points) < 2:
            return None
        return points[-1]["value"] - points[0]["value"]


def build(user: User, start: date_type, end: date_type) -> Report:
    """Assemble le rapport d'une période."""
    daily = analysis.daily_totals(user, start, end)
    weight = charts.series(user, "weight", start, end)
    weights = {point["date"]: point["value"] for point in weight["points"]}

    days = []
    for day in sorted(daily):
        values = daily[day]
        targets = resolve_for_date(user, day)
        days.append(
            DayRow(
                date=day,
                totals=values["totals"],
                incomplete_nutrients=values["incomplete_nutrients"],
                entries=values["entries"],
                target_calories=(targets or {}).get("daily_calories"),
                weight_kg=weights.get(day),
            )
        )

    calories = analysis.nutrient_sources(
        user, nutrient="energy_kcal", start=start, end=end, limit=5
    )

    return Report(
        start=start,
        end=end,
        days=days,
        averages=analysis.averages(daily, SUMMARY_NUTRIENTS),
        adherence=analysis.goal_adherence(user, daily),
        weight=weight,
        top_foods=calories.sources,
    )


def _decimal(value: Decimal | None) -> str:
    """Représentation non localisée, et **vide** quand la valeur est inconnue.

    Un zéro affirmerait que le nutriment vaut zéro (spec 01 §8) ; une virgule
    décimale ferait dériver la colonne dans un tableur configuré autrement.
    """
    if value is None:
        return ""
    return f"{Decimal(value).quantize(Decimal('0.01')):f}"


def to_csv(report: Report) -> str:
    """Une ligne par journée tenue, un en-tête stable (spec 04 §17)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["date", "entrées", "objectif_kcal", "poids_kg", *CSV_NUTRIENTS])

    for row in report.days:
        writer.writerow(
            [
                row.date.isoformat(),
                row.entries,
                _decimal(row.target_calories),
                _decimal(row.weight_kg),
                *(_decimal(row.totals.get(name)) for name in CSV_NUTRIENTS),
            ]
        )

    return buffer.getvalue()


def to_pdf(report: Report) -> bytes:
    """Résumé imprimable de la période.

    ReportLab est importé ici, et non au chargement du module : le reste de
    l'application n'a pas à en dépendre pour démarrer.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdf_canvas

    buffer = io.BytesIO()
    page = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    y = height - 25 * mm

    page.setTitle(f"MyFitnessPalworld — {report.start:%d/%m/%Y} au {report.end:%d/%m/%Y}")

    page.setFont("Helvetica-Bold", 16)
    page.drawString(left, y, "MyFitnessPalworld — rapport")
    y -= 8 * mm

    page.setFont("Helvetica", 11)
    page.drawString(left, y, f"Du {report.start:%d/%m/%Y} au {report.end:%d/%m/%Y}")
    y -= 6 * mm

    # Le dénominateur des moyennes est écrit noir sur blanc : sans lui, « 1 640
    # kcal par jour » ne dit pas sur combien de jours.
    page.drawString(
        left,
        y,
        f"{report.logged_days} journée(s) journalisée(s) sur {report.calendar_days}",
    )
    y -= 10 * mm

    y = _pdf_averages(page, report, left, y, mm)
    y = _pdf_adherence(page, report, left, y, mm)
    y = _pdf_top_foods(page, report, left, y, mm)
    _pdf_weight(page, report, left, y, width, mm)

    page.showPage()
    page.save()
    return buffer.getvalue()


def _pdf_averages(page, report: Report, left: float, y: float, mm: float) -> float:
    page.setFont("Helvetica-Bold", 12)
    page.drawString(left, y, "Moyennes par journée journalisée")
    y -= 7 * mm
    page.setFont("Helvetica", 10)

    if not report.days:
        page.drawString(left, y, "Aucune journée journalisée sur la période.")
        return y - 10 * mm

    for name in SUMMARY_NUTRIENTS:
        value = report.averages.get(name)
        # « — » et non « 0 » : personne n'a mesuré ce nutriment.
        shown = "—" if value is None else _decimal(value)
        page.drawString(left, y, f"{nutrient_label(name)} : {shown}")
        y -= 5.5 * mm

    return y - 5 * mm


def _pdf_adherence(page, report: Report, left: float, y: float, mm: float) -> float:
    page.setFont("Helvetica-Bold", 12)
    page.drawString(left, y, "Respect de l'objectif calorique")
    y -= 7 * mm
    page.setFont("Helvetica", 10)

    measured = report.adherence.get("days_measured", 0)
    if not measured:
        page.drawString(left, y, "Aucun objectif applicable sur la période.")
        return y - 10 * mm

    within = report.adherence.get("days_within_goal", 0)
    tolerance = int(analysis.CALORIE_TOLERANCE * 100)
    page.drawString(left, y, f"{within} journée(s) sur {measured} à ±{tolerance} % de l'objectif")
    return y - 10 * mm


def _pdf_top_foods(page, report: Report, left: float, y: float, mm: float) -> float:
    page.setFont("Helvetica-Bold", 12)
    page.drawString(left, y, "Aliments les plus caloriques")
    y -= 7 * mm
    page.setFont("Helvetica", 10)

    if not report.top_foods:
        page.drawString(left, y, "Aucun aliment journalisé.")
        return y - 10 * mm

    for source in report.top_foods:
        page.drawString(
            left,
            y,
            f"{source.name} — {_decimal(source.total)} kcal ({source.share:.0f} %)",
        )
        y -= 5.5 * mm

    return y - 5 * mm


def _pdf_weight(page, report: Report, left: float, y: float, width: float, mm: float) -> None:
    page.setFont("Helvetica-Bold", 12)
    page.drawString(left, y, "Poids")
    y -= 7 * mm
    page.setFont("Helvetica", 10)

    points = report.weight.get("points") or []
    if not points:
        page.drawString(left, y, "Aucune pesée sur la période.")
        return

    change = report.weight_change
    résumé = f"{_decimal(points[-1]['value'])} kg"
    if change is not None:
        résumé += f" ({'+' if change > 0 else ''}{_decimal(change)} kg sur la période)"
    page.drawString(left, y, résumé)
    y -= 8 * mm

    if len(points) < 2:
        return

    # Courbe tracée à la main : une bibliothèque de graphiques de plus pour une
    # polyligne ne se justifierait pas.
    values = [float(point["value"]) for point in points]
    low, high = min(values), max(values)
    span = high - low or 1.0
    chart_width = width - 2 * left
    chart_height = 35 * mm
    bottom = y - chart_height

    page.setLineWidth(0.5)
    page.rect(left, bottom, chart_width, chart_height, stroke=1, fill=0)

    step = chart_width / (len(values) - 1)
    page.setLineWidth(1)
    for index in range(len(values) - 1):
        page.line(
            left + index * step,
            bottom + (values[index] - low) / span * chart_height,
            left + (index + 1) * step,
            bottom + (values[index + 1] - low) / span * chart_height,
        )

    # Les **extrémités** de la courbe, pas son minimum et son maximum : sous
    # une ligne descendante, « 79,1 » à gauche et « 80,0 » à droite se lisent
    # comme une prise de poids.
    page.setFont("Helvetica", 8)
    page.drawString(left, bottom - 4 * mm, f"{points[0]['date']:%d/%m} · {values[0]:.1f} kg")
    page.drawRightString(
        left + chart_width, bottom - 4 * mm, f"{points[-1]['date']:%d/%m} · {values[-1]:.1f} kg"
    )
