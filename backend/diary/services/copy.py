"""Duplication et copie d'entrées de journal (spec 01 §5, spec 04 §4).

La règle décisive de ce module est celle de la spec 01 §5 :

    Une copie/duplication normale repart de la **version actuelle** de
    l'aliment. Les entrées historiques déjà existantes restent basées sur leur
    snapshot.

Elle semble contredire l'immuabilité posée à l'étape 6, mais la complète.
Modifier une entrée existante, c'est corriger une consommation passée : son
snapshot fait foi. La dupliquer, c'est déclarer une **nouvelle** consommation :
elle repart des valeurs actuelles de l'aliment.

L'implémentation naïve — recopier la ligne — donne le mauvais résultat
silencieusement : la copie porterait des valeurs périmées sans que rien ne le
signale.

La règle vaut pour les **trois** natures d'entrée. Une recette n'a pas de
`food_id` : ne traiter que l'aliment la ferait tomber dans le repli prévu pour
les sources disparues, et sa copie porterait l'ancienne version de la recette
sans que rien ne l'indique.
"""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from diary.models import DiaryEntry, MealType
from diary.services.day import day_entries
from diary.services.entries import (
    build_food_snapshot,
    build_recipe_snapshot,
    create_food_entry,
    get_or_create_day,
)
from nutrition.models import Food
from nutrition.services.quantities import resolve_factor
from nutrition.services.search import record_food_usage
from recipes.models import Recipe

#: Champs de saisie recopiés tels quels : ils décrivent ce qui a été mangé,
#: pas ce que valait l'aliment.
_CARRIED_FIELDS = ("entry_type", "quantity", "unit_label", "note")


def _current_food(user: User, entry: DiaryEntry) -> Food | None:
    """Version actuelle de l'aliment, si elle est encore visible par l'appelant."""
    if entry.food_id is None:
        return None

    return (
        Food.objects.visible_to(user)
        .select_related("nutrition")
        .prefetch_related("portions")
        .filter(pk=entry.food_id)
        .first()
    )


def _current_recipe(user: User, entry: DiaryEntry) -> Recipe | None:
    """Version actuelle de la recette, si elle est encore visible par l'appelant."""
    if entry.recipe_id is None:
        return None

    return Recipe.objects.visible_to(user).filter(pk=entry.recipe_id).first()


def _shift_time(consumed_at: datetime, day: date_type) -> datetime:
    """Conserve l'heure, change la date (spec 01 §5 : « horaires copiés »)."""
    return consumed_at.replace(year=day.year, month=day.month, day=day.day)


@transaction.atomic
def copy_entry(
    *,
    user: User,
    entry: DiaryEntry,
    day: date_type,
    meal_type: MealType | None = None,
) -> DiaryEntry:
    """Crée une nouvelle entrée à partir d'une existante.

    Repart des valeurs actuelles de la source quand elle est encore là :
    l'aliment pour une entrée d'aliment, la recette pour une entrée de recette.
    Sinon — source supprimée, devenue invisible, ou entrée d'ajout rapide — le
    snapshot stocké est recopié tel quel : refuser ferait échouer la copie
    d'une journée entière pour un seul produit disparu.
    """
    food = _current_food(user, entry)
    recipe = _current_recipe(user, entry) if food is None else None

    unit_factor = entry.snapshot_unit_factor

    if food is not None:
        snapshot = build_food_snapshot(food)
        try:
            # L'unité peut avoir cessé d'être calculable — une portion supprimée
            # entre-temps, par exemple. Le facteur figé prend alors le relais
            # plutôt que de faire échouer la copie.
            unit_factor = resolve_factor(food, entry.unit_label)
        except ValidationError:
            unit_factor = entry.snapshot_unit_factor
    elif recipe is not None:
        # Une portion vaut une portion : le facteur reste à 1, seul le contenu
        # de la recette a pu changer.
        snapshot = build_recipe_snapshot(recipe)
    else:
        snapshot = _stored_snapshot(entry)

    copied = DiaryEntry.objects.create(
        diary_day=get_or_create_day(user, day),
        meal_type=meal_type or entry.meal_type,
        consumed_at=_shift_time(entry.consumed_at, day),
        food=food,
        recipe=recipe,
        snapshot_unit_factor=unit_factor,
        **{field: getattr(entry, field) for field in _CARRIED_FIELDS},
        **snapshot,
    )

    if food is not None:
        record_food_usage(user, food)

    return copied


def _stored_snapshot(entry: DiaryEntry) -> dict:
    """Snapshot de l'entrée d'origine, recopié à l'identique."""
    fields = [field.name for field in DiaryEntry._meta.fields if field.name.startswith("snapshot_")]
    return {name: getattr(entry, name) for name in fields if name != "snapshot_unit_factor"}


@transaction.atomic
def copy_meal(
    *,
    user: User,
    source_day: date_type,
    source_meal_type: MealType,
    target_days: list[date_type],
    target_meal_type: MealType | None = None,
) -> list[DiaryEntry]:
    """Copie un repas vers une ou plusieurs dates."""
    entries = [
        entry
        for entry in day_entries(user, source_day)
        if entry.meal_type_id == source_meal_type.id
    ]

    copied = []
    for day in target_days:
        for entry in entries:
            copied.append(copy_entry(user=user, entry=entry, day=day, meal_type=target_meal_type))

    return copied


@transaction.atomic
def copy_day(
    *, user: User, source_day: date_type, target_days: list[date_type]
) -> list[DiaryEntry]:
    """Copie une journée entière, chaque entrée retrouvant son repas.

    Les entrées existantes des journées cibles sont conservées : une copie
    s'ajoute, elle n'écrase jamais.
    """
    entries = day_entries(user, source_day)

    copied = []
    for day in target_days:
        for entry in entries:
            copied.append(copy_entry(user=user, entry=entry, day=day))

    return copied


@transaction.atomic
def add_food_on_days(
    *,
    user: User,
    food: Food,
    days: list[date_type],
    meal_type: MealType,
    quantity: Decimal,
    unit_label: str,
    consumed_at: datetime,
) -> list[DiaryEntry]:
    """Ajoute un même aliment sur plusieurs dates (spec 01 §5).

    Chaque date reçoit une entrée indépendante, snapshotée depuis la version
    actuelle de l'aliment.
    """
    return [
        create_food_entry(
            user=user,
            food=food,
            day=day,
            meal_type=meal_type,
            quantity=quantity,
            unit_label=unit_label,
            consumed_at=_shift_time(consumed_at, day),
        )
        for day in days
    ]
