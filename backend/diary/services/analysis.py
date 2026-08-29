"""Analyse du journal sur une période (spec 01 §21-22).

Deux règles gouvernent ce module, et ce sont deux visages de la même :

> **Ce qui n'a pas été mesuré ne vaut pas zéro.**

Au niveau du nutriment : une entrée qui ne renseigne pas les protéines rend le
total partiel. Le pourcentage de contribution de chaque aliment est alors
calculé sur un dénominateur sous-estimé — tous sont donc surévalués, et l'écran
doit le dire plutôt que de laisser croire qu'ils somment à cent (spec 01 §8).

Au niveau de la journée : une journée sans aucune entrée n'est pas une journée
à zéro calorie, c'est une journée qu'on n'a pas journalisée. Diviser par sept
une semaine tenue cinq jours produit un chiffre plausible et faux. **Les
moyennes portent sur les journées tenues**, et leur nombre s'affiche à côté.

Les valeurs viennent des snapshots des entrées : une fiche corrigée après coup
ne réécrit pas l'historique (spec 01 §6).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal

from accounts.models import User
from diary.models import DiaryEntry
from diary.services.entries import computed_nutrition
from nutrition.models.nutrients import NUTRIENT_FIELDS
from nutrition.services.aggregation import sum_values
from nutrition.services.goals import resolve_for_date

#: Combien d'aliments le classement renvoie. Au-delà, ce ne sont plus des
#: « principales sources » (spec 01 §21).
TOP_SOURCES = 15

#: Tolérance retenue pour dire qu'une journée a respecté son objectif calorique.
#: La même que celle du planning (spec 01 §15) : deux seuils différents pour la
#: même idée finiraient par se contredire.
CALORIE_TOLERANCE = Decimal("0.05")


@dataclass
class Source:
    """Un aliment et ce qu'il a apporté sur la période."""

    name: str
    total: Decimal
    entries: int
    #: Part du total connu. Un minorant quand le total est partiel.
    share: float = 0.0


@dataclass
class NutrientAnalysis:
    nutrient: str
    start: date_type
    end: date_type
    total: Decimal | None
    sources: list[Source] = field(default_factory=list)
    #: Entrées qui ne renseignent pas ce nutriment. Elles ne valent pas zéro.
    unknown_entries: int = 0
    logged_days: int = 0

    @property
    def is_partial(self) -> bool:
        return self.unknown_entries > 0


def period_entries(user: User, start: date_type, end: date_type):
    """Entrées du journal sur l'intervalle, bornes comprises."""
    return (
        DiaryEntry.objects.filter(
            diary_day__user=user, diary_day__date__gte=start, diary_day__date__lte=end
        )
        .select_related("diary_day")
        .order_by("diary_day__date", "consumed_at", "id")
    )


def logged_days(user: User, start: date_type, end: date_type) -> list[date_type]:
    """Journées qui portent au moins une entrée.

    C'est le dénominateur de toutes les moyennes : les autres n'ont pas été
    tenues, et les compter reviendrait à affirmer qu'on n'y a rien mangé.
    """
    return sorted(
        set(
            DiaryEntry.objects.filter(
                diary_day__user=user, diary_day__date__gte=start, diary_day__date__lte=end
            ).values_list("diary_day__date", flat=True)
        )
    )


def nutrient_sources(
    user: User, *, nutrient: str, start: date_type, end: date_type, limit: int = TOP_SOURCES
) -> NutrientAnalysis:
    """D'où vient un nutriment sur la période (spec 01 §21).

    Le regroupement se fait sur le **nom du snapshot** : c'est ce que
    l'utilisateur lit, et cela reste juste pour un aliment supprimé depuis.
    """
    totals: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    unknown = 0

    for entry in period_entries(user, start, end):
        value = computed_nutrition(entry).get(nutrient)
        if value is None:
            # Comptée comme inconnue, jamais comme nulle : c'est ce qui rend le
            # total partiel et les parts minorantes.
            unknown += 1
            continue
        totals[entry.snapshot_name] += value
        counts[entry.snapshot_name] += 1

    grand_total = sum(totals.values(), Decimal(0)) if totals else None

    sources = [
        Source(
            name=name,
            total=total,
            entries=counts[name],
            share=float(total / grand_total * 100) if grand_total else 0.0,
        )
        for name, total in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    ]

    return NutrientAnalysis(
        nutrient=nutrient,
        start=start,
        end=end,
        total=grand_total,
        sources=sources[:limit],
        unknown_entries=unknown,
        logged_days=len(logged_days(user, start, end)),
    )


def daily_totals(user: User, start: date_type, end: date_type) -> dict[date_type, dict]:
    """Totaux par journée **tenue**. Les journées vides n'y figurent pas."""
    by_day: dict[date_type, list[DiaryEntry]] = defaultdict(list)
    for entry in period_entries(user, start, end):
        by_day[entry.diary_day.date].append(entry)

    results: dict[date_type, dict] = {}

    for day, entries in by_day.items():
        totals, incomplete = sum_values(
            (computed_nutrition(entry) for entry in entries), NUTRIENT_FIELDS
        )
        results[day] = {
            "totals": totals,
            "incomplete_nutrients": incomplete,
            "entries": len(entries),
        }

    return results


def averages(daily: dict[date_type, dict], nutrients: tuple[str, ...]) -> dict[str, Decimal | None]:
    """Moyennes sur les journées tenues, et sur elles seules.

    Un nutriment qu'aucune journée ne renseigne reste `None` : là, on ne sait
    pas. Une journée qui ne le renseigne pas est exclue de sa moyenne à lui,
    pas des autres.
    """
    result: dict[str, Decimal | None] = {}

    for nutrient in nutrients:
        values = [
            day["totals"][nutrient]
            for day in daily.values()
            if day["totals"].get(nutrient) is not None
        ]
        result[nutrient] = sum(values, Decimal(0)) / len(values) if values else None

    return result


def goal_adherence(user: User, daily: dict[date_type, dict]) -> dict:
    """Combien de journées tenues ont respecté leur objectif calorique.

    L'objectif est celui **de chaque date**, surcharge de jour de semaine
    comprise : un objectif du dimanche ne juge pas un mardi (spec 01 §4).
    """
    within = 0
    measured = 0

    for day, values in daily.items():
        targets = resolve_for_date(user, day)
        consumed = values["totals"].get("energy_kcal")
        target = targets.get("daily_calories") if targets else None

        if target is None or Decimal(target) == 0 or consumed is None:
            continue

        measured += 1
        deviation = abs(Decimal(consumed) - Decimal(target)) / Decimal(target)
        if deviation <= CALORIE_TOLERANCE:
            within += 1

    return {"days_measured": measured, "days_within_goal": within}
