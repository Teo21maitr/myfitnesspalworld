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
from nutrition.services.aggregation import sum_values
from nutrition.services.quantities import multiplier, resolve_factor
from nutrition.services.search import record_food_usage
from recipes.services.nutrition import ensure_fresh

#: Une entrée d'ajout rapide porte ses valeurs telles quelles.
QUICK_ADD_REFERENCE_AMOUNT = Decimal("1")
QUICK_ADD_UNIT_LABEL = "portion"

#: Nutriments modifiables sur un ajout rapide (spec 01 §12).
QUICK_ADD_FIELDS = ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")

#: Une entrée de recette se compte en portions, comme un ajout rapide : sa
#: référence vaut une portion, et sa quantité leur nombre.
RECIPE_REFERENCE_AMOUNT = Decimal("1")
RECIPE_UNIT_LABEL = "portion"


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


def build_recipe_snapshot(recipe) -> dict:
    """Recopie l'identité et la nutrition **par portion** d'une recette.

    Le cache est rafraîchi au passage : journaliser une recette dont un
    ingrédient a changé depuis doit partir des valeurs à jour.
    """
    nutrition = ensure_fresh(recipe)

    snapshot = {
        "snapshot_name": recipe.name,
        "snapshot_brand": "",
        "snapshot_source": EntryType.RECIPE,
        "snapshot_reference_amount": RECIPE_REFERENCE_AMOUNT,
        "snapshot_reference_unit": UnitType.UNIT,
    }

    for field in SNAPSHOT_NUTRIENT_FIELDS:
        snapshot[field] = getattr(nutrition, field.removeprefix("snapshot_"), None)

    return snapshot


@transaction.atomic
def create_recipe_entry(
    *,
    user: User,
    recipe,
    day: date_type,
    meal_type: MealType,
    servings: Decimal,
    consumed_at,
    note: str = "",
) -> DiaryEntry:
    """Journalise N portions d'une recette (spec 01 §14).

    Une seule entrée, pas une par ingrédient : c'est le plat qui a été mangé.
    Elle emprunte la forme de l'ajout rapide — une référence d'une portion,
    comptée en unités — car une portion se compte et ne se pèse pas.
    """
    return DiaryEntry.objects.create(
        diary_day=get_or_create_day(user, day),
        meal_type=meal_type,
        entry_type=EntryType.RECIPE,
        consumed_at=consumed_at,
        quantity=servings,
        unit_label=RECIPE_UNIT_LABEL,
        note=note,
        recipe=recipe,
        snapshot_unit_factor=Decimal("1"),
        **build_recipe_snapshot(recipe),
    )


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

    La règle « inconnu n'est pas zéro » vit dans `nutrition.services.aggregation`,
    partagée avec les recettes : l'écrire ici aussi la ferait diverger.
    """
    names = [field.removeprefix("snapshot_") for field in SNAPSHOT_NUTRIENT_FIELDS]

    return sum_values((computed_nutrition(entry) for entry in entries), names)
