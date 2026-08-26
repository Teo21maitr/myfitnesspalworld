"""Création, calcul et agrégation des entrées de journal (spec 01 §5, §6, §12).

Le snapshot recopié ici est la donnée historique de vérité : il porte les
valeurs **pour la quantité de référence**, jamais les valeurs consommées. Voir
l'en-tête de `diary.models` pour le raisonnement.
"""

from datetime import date as date_type
from decimal import Decimal

from django.db import transaction

from accounts.models import User
from diary.models import SNAPSHOT_NUTRIENT_FIELDS, DiaryDay, DiaryEntry, EntryType, MealType
from nutrition.models import Food, UnitType
from nutrition.services.quantities import multiplier, resolve_factor
from nutrition.services.search import record_food_usage

#: Une entrée d'ajout rapide porte ses valeurs telles quelles.
QUICK_ADD_REFERENCE_AMOUNT = Decimal("1")
QUICK_ADD_UNIT_LABEL = "portion"

#: Nutriments modifiables sur un ajout rapide (spec 01 §12).
QUICK_ADD_FIELDS = ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")


def get_or_create_day(user: User, day: date_type) -> DiaryDay:
    """Journée du journal, créée à la volée. Passé, présent et futur (spec 01 §5)."""
    diary_day, _ = DiaryDay.objects.get_or_create(user=user, date=day)
    return diary_day


def build_food_snapshot(food: Food) -> dict:
    """Recopie l'identité et la nutrition d'un aliment dans un snapshot."""
    nutrition = getattr(food, "nutrition", None)

    snapshot = {
        "snapshot_name": food.name,
        "snapshot_brand": food.brand,
        "snapshot_source": food.source,
        "snapshot_reference_amount": food.reference_amount,
        "snapshot_reference_unit": food.reference_unit,
    }

    for field in SNAPSHOT_NUTRIENT_FIELDS:
        source_field = field.removeprefix("snapshot_")
        snapshot[field] = getattr(nutrition, source_field, None) if nutrition else None

    return snapshot


@transaction.atomic
def create_food_entry(
    *,
    user: User,
    food: Food,
    day: date_type,
    meal_type: MealType,
    quantity: Decimal,
    unit_label: str,
    consumed_at,
    note: str = "",
) -> DiaryEntry:
    """Journalise un aliment.

    L'unité est résolue maintenant et son facteur figé dans l'entrée : celle-ci
    doit rester calculable même si l'aliment ou sa portion disparaît ensuite.
    """
    factor = resolve_factor(food, unit_label)

    entry = DiaryEntry.objects.create(
        diary_day=get_or_create_day(user, day),
        meal_type=meal_type,
        entry_type=EntryType.FOOD,
        consumed_at=consumed_at,
        quantity=quantity,
        unit_label=unit_label,
        note=note,
        food=food,
        snapshot_unit_factor=factor,
        **build_food_snapshot(food),
    )

    # C'est ici que les listes « récents » et « fréquents » prennent vie, ainsi
    # que les trois premiers critères du classement de la recherche.
    record_food_usage(user, food)

    return entry


@transaction.atomic
def create_quick_add_entry(
    *,
    user: User,
    day: date_type,
    meal_type: MealType,
    consumed_at,
    values: dict,
    note: str = "",
) -> DiaryEntry:
    """Crée un ajout rapide : des calories, éventuellement des macros (spec 01 §12)."""
    snapshot = dict.fromkeys(SNAPSHOT_NUTRIENT_FIELDS)
    for field in QUICK_ADD_FIELDS:
        snapshot[f"snapshot_{field}"] = values.get(field)

    return DiaryEntry.objects.create(
        diary_day=get_or_create_day(user, day),
        meal_type=meal_type,
        entry_type=EntryType.QUICK_ADD,
        consumed_at=consumed_at,
        quantity=Decimal("1"),
        unit_label=QUICK_ADD_UNIT_LABEL,
        note=note,
        snapshot_name=values.get("name") or "Ajout rapide",
        snapshot_source=EntryType.QUICK_ADD,
        snapshot_reference_amount=QUICK_ADD_REFERENCE_AMOUNT,
        snapshot_reference_unit=UnitType.UNIT,
        snapshot_unit_factor=Decimal("1"),
        **snapshot,
    )


def entry_multiplier(entry: DiaryEntry) -> Decimal:
    """Facteur à appliquer au snapshot, calculé depuis l'entrée seule."""
    return multiplier(entry.snapshot_reference_amount, entry.quantity, entry.snapshot_unit_factor)


def computed_nutrition(entry: DiaryEntry) -> dict[str, Decimal | None]:
    """Valeurs réellement consommées par cette entrée.

    Une valeur inconnue le reste : elle n'est jamais ramenée à zéro par la
    multiplication (spec 01 §8).
    """
    factor = entry_multiplier(entry)

    values: dict[str, Decimal | None] = {}
    for field in SNAPSHOT_NUTRIENT_FIELDS:
        reference = getattr(entry, field)
        name = field.removeprefix("snapshot_")
        values[name] = None if reference is None else (Decimal(reference) * factor)

    return values


def sum_nutrition(entries) -> tuple[dict[str, Decimal | None], list[str]]:
    """Totalise plusieurs entrées.

    Renvoie les totaux et la liste des nutriments dont au moins une entrée
    n'était pas renseignée. Additionner en ignorant les inconnues reviendrait à
    les compter pour zéro : le total reste utile, mais il est signalé comme
    partiel plutôt que présenté comme exact (spec 01 §8).

    Sans aucune entrée, les totaux valent zéro et non « inconnu » : on sait que
    rien n'a été consommé.
    """
    names = [field.removeprefix("snapshot_") for field in SNAPSHOT_NUTRIENT_FIELDS]

    # Rien de consommé n'est pas une donnée manquante : c'est zéro. La nuance
    # compte à l'écran, où « — » signifie « on ne sait pas » (spec 01 §8).
    if not entries:
        return dict.fromkeys(names, Decimal(0)), []

    # Toujours la même forme : le frontend n'a pas à distinguer « nutriment
    # absent de la réponse » de « inconnu ».
    totals: dict[str, Decimal | None] = dict.fromkeys(names)
    known: dict[str, bool] = {}
    incomplete: set[str] = set()

    for entry in entries:
        for name, value in computed_nutrition(entry).items():
            if value is None:
                incomplete.add(name)
                totals.setdefault(name, None)
                continue

            totals[name] = value if not known.get(name) else totals[name] + value
            known[name] = True

    # Un nutriment qu'aucune entrée ne renseigne reste inconnu, pas nul.
    for name in totals:
        if not known.get(name):
            totals[name] = None

    return totals, sorted(incomplete & set(known))
