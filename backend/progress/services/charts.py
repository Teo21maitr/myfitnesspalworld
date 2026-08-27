"""Séries de progression pour les graphiques (spec 01 §19, spec 04 §14).

La spec demande une « moyenne mobile 7 jours ». Moyenner les sept dernières
saisies serait faux : on ne se pèse pas tous les jours, et pour qui se pèse
une fois par semaine cette moyenne couvrirait sept semaines. La fenêtre est
donc **calendaire** — les mesures tombant dans `[d - 6 jours, d]` — quel que
soit leur nombre.

Aucun point n'est fabriqué pour les jours sans mesure : interpoler
produirait des valeurs qui n'ont jamais été relevées.
"""

from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from decimal import Decimal

from django.db.models import Model

from accounts.models import User
from progress.models import BodyMeasurementEntry, WeightEntry

#: Largeur de la fenêtre de lissage, bornes comprises.
MOVING_AVERAGE_DAYS = 7

#: Période affichée quand l'appelant n'en précise aucune.
DEFAULT_PERIOD_DAYS = 90

#: Au-delà, la réponse deviendrait volumineuse sans gagner en lisibilité.
MAX_PERIOD_DAYS = 730

#: Précision de la tendance, exprimée par semaine.
TREND_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class Metric:
    """Ce qu'il faut savoir d'une métrique pour en tracer la courbe."""

    model: type[Model]
    field: str
    unit: str
    #: Seul le poids a une cible, portée par le profil (spec 01 §2).
    has_target: bool = False


METRICS: dict[str, Metric] = {
    "weight": Metric(WeightEntry, "weight_kg", "kg", has_target=True),
    "waist": Metric(BodyMeasurementEntry, "waist_cm", "cm"),
    "hips": Metric(BodyMeasurementEntry, "hips_cm", "cm"),
    "chest": Metric(BodyMeasurementEntry, "chest_cm", "cm"),
    "arm": Metric(BodyMeasurementEntry, "arm_cm", "cm"),
    "thigh": Metric(BodyMeasurementEntry, "thigh_cm", "cm"),
    "body_fat": Metric(BodyMeasurementEntry, "body_fat_percent", "%"),
}


def series(user: User, metric_key: str, start: date_type, end: date_type) -> dict:
    """Points, moyenne mobile, cible et tendance sur l'intervalle demandé."""
    metric = METRICS[metric_key]
    precision = _precision(metric)

    # Le lissage remonte avant `start` : une mesure de la veille appartient à
    # la fenêtre du premier point affiché. Sans cela, la moyenne d'une même
    # date changerait selon la période demandée — sur 30 jours puis sur 90.
    lookback = start - timedelta(days=MOVING_AVERAGE_DAYS - 1)
    measured = _measurements(user, metric, lookback, end)

    averages = _moving_averages(measured, precision)
    points = [
        {"date": day, "value": value, "moving_average": average}
        for (day, value), average in zip(measured, averages, strict=True)
        if day >= start
    ]

    return {
        "metric": metric_key,
        "unit": metric.unit,
        "from": start,
        "to": end,
        "points": points,
        "target": _target(user) if metric.has_target else None,
        "trend_per_week": _trend_per_week([(p["date"], p["value"]) for p in points]),
    }


def _measurements(
    user: User, metric: Metric, start: date_type, end: date_type
) -> list[tuple[date_type, Decimal]]:
    """Mesures relevées sur l'intervalle, par date croissante.

    Une entrée de mensurations peut ne porter qu'une partie des mesures : les
    valeurs absentes sont exclues plutôt que comptées pour zéro.
    """
    rows = (
        metric.model.objects.filter(
            user=user,
            date__gte=start,
            date__lte=end,
            **{f"{metric.field}__isnull": False},
        )
        .order_by("date")
        .values_list("date", metric.field)
    )
    return list(rows)


def _moving_averages(
    measured: list[tuple[date_type, Decimal]], precision: Decimal
) -> list[Decimal]:
    """Moyenne des mesures de la fenêtre calendaire close par chaque point."""
    averages: list[Decimal] = []
    window_start = 0

    for index, (day, _) in enumerate(measured):
        oldest = day - timedelta(days=MOVING_AVERAGE_DAYS - 1)
        # Les dates croissent : le début de fenêtre ne recule jamais.
        while measured[window_start][0] < oldest:
            window_start += 1

        window = measured[window_start : index + 1]
        total = sum((value for _, value in window), Decimal(0))
        averages.append((total / len(window)).quantize(precision))

    return averages


def _trend_per_week(points: list[tuple[date_type, Decimal]]) -> Decimal | None:
    """Pente hebdomadaire, par moindres carrés sur les mesures réelles.

    Régresser sur la moyenne mobile surpondérerait les périodes de mesure
    dense. Sous deux points il n'y a pas de tendance à établir : `None`, pas
    zéro, qui affirmerait une stagnation.
    """
    if len(points) < 2:
        return None

    origin = points[0][0]
    xs = [Decimal((day - origin).days) for day, _ in points]
    ys = [value for _, value in points]
    count = Decimal(len(points))

    sum_x = sum(xs, Decimal(0))
    sum_y = sum(ys, Decimal(0))
    sum_xy = sum((x * y for x, y in zip(xs, ys, strict=True)), Decimal(0))
    sum_x2 = sum((x * x for x in xs), Decimal(0))

    denominator = count * sum_x2 - sum_x * sum_x
    if denominator == 0:
        # Toutes les mesures au même jour : aucune pente définissable.
        return None

    slope_per_day = (count * sum_xy - sum_x * sum_y) / denominator
    return (slope_per_day * 7).quantize(TREND_PRECISION)


def _precision(metric: Metric) -> Decimal:
    """Précision d'affichage, reprise du champ pour ne pas en inventer une."""
    decimals = metric.model._meta.get_field(metric.field).decimal_places
    return Decimal(1).scaleb(-decimals)


def _target(user: User) -> Decimal | None:
    profile = getattr(user, "profile", None)
    return getattr(profile, "target_weight_kg", None)
