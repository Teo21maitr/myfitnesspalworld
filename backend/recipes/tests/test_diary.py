"""Recettes au journal (spec 01 §5, §6 et §14).

Deux règles voisines qu'il serait facile de confondre :

- modifier une recette ne touche **jamais** les entrées déjà journalisées ;
- **dupliquer** une entrée de recette repart de la version **actuelle**.

La seconde est le piège de cette étape : une entrée de recette n'a pas de
`food_id`, et un `copy_entry` qui ne connaîtrait que les aliments la ferait
tomber dans le repli prévu pour les sources disparues.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from diary.models import DiaryEntry, EntryType
from diary.services import copy as copy_service
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from recipes.models import Recipe, RecipeIngredient
from recipes.services import nutrition as nutrition_service

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 26)
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def meal(active_user):
    return meal_types_for(active_user).first()


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"))
    return food


@pytest.fixture
def recipe(active_user, chicken) -> Recipe:
    """Deux portions à 200 kcal : 200 g de poulet valent 400 kcal."""
    recipe = Recipe.objects.create(owner=active_user, name="Poulet rôti", servings=Decimal("2"))
    RecipeIngredient.objects.create(
        recipe=recipe,
        food=chicken,
        food_name=chicken.name,
        quantity=Decimal("200"),
        unit_label="g",
    )
    nutrition_service.refresh(recipe)
    return recipe


def moment(day: date, hour: int = 12):
    return timezone.make_aware(timezone.datetime(day.year, day.month, day.day, hour, 30))


def journal(user, recipe, meal, servings="2", day=TODAY) -> DiaryEntry:
    return entries_service.create_recipe_entry(
        user=user,
        recipe=recipe,
        day=day,
        meal_type=meal,
        servings=Decimal(servings),
        consumed_at=moment(day),
    )


def kcal(entry: DiaryEntry) -> Decimal:
    return entries_service.computed_nutrition(entry)["energy_kcal"]


def enrich(recipe, chicken):
    """Double la quantité de poulet : la portion passe de 200 à 400 kcal."""
    ingredient = recipe.ingredients.first()
    ingredient.quantity = Decimal("400")
    ingredient.save()
    nutrition_service.refresh(recipe)


# --- Journaliser ------------------------------------------------------------


def test_une_recette_produit_une_seule_entree(active_user, recipe, meal):
    """C'est le plat qui a été mangé, pas ses ingrédients un à un."""
    journal(active_user, recipe, meal)

    assert DiaryEntry.objects.count() == 1
    entry = DiaryEntry.objects.get()
    assert entry.entry_type == EntryType.RECIPE
    assert entry.unit_label == "portion"


def test_les_portions_multiplient_les_valeurs(active_user, recipe, meal):
    assert kcal(journal(active_user, recipe, meal, servings="2")) == Decimal("400")
    assert kcal(journal(active_user, recipe, meal, servings="1")) == Decimal("200")


def test_lentree_garde_son_snapshot_quand_la_recette_change(active_user, recipe, meal, chicken):
    """Modifier une recette ne modifie jamais l'historique (spec 01 §14)."""
    entry = journal(active_user, recipe, meal)
    enrich(recipe, chicken)

    entry.refresh_from_db()
    assert kcal(entry) == Decimal("400")


def test_lentree_survit_a_la_suppression_de_la_recette(active_user, recipe, meal):
    entry = journal(active_user, recipe, meal)
    recipe.delete()

    entry.refresh_from_db()
    assert entry.recipe_id is None
    assert kcal(entry) == Decimal("400")


def test_journaliser_rafraichit_un_cache_perime(active_user, recipe, meal, chicken):
    """Une recette dont un ingrédient a changé part des valeurs à jour."""
    chicken.nutrition.energy_kcal = Decimal("400")
    chicken.nutrition.save()
    chicken.save()

    assert kcal(journal(active_user, recipe, meal, servings="1")) == Decimal("400")


# --- Le piège : dupliquer repart de la recette actuelle ----------------------


def test_dupliquer_une_entree_de_recette_repart_des_valeurs_actuelles(
    active_user, recipe, meal, chicken
):
    """La règle de la spec 01 §5, appliquée aux recettes.

    Sans elle, la copie retomberait sur le snapshot stocké et porterait des
    valeurs périmées, sans que rien ne le signale à l'écran.
    """
    entry = journal(active_user, recipe, meal, servings="2")
    enrich(recipe, chicken)

    copied = copy_service.copy_entry(user=active_user, entry=entry, day=TOMORROW)

    assert kcal(copied) == Decimal("800")
    entry.refresh_from_db()
    assert kcal(entry) == Decimal("400")


def test_la_copie_reste_liee_a_la_recette(active_user, recipe, meal):
    entry = journal(active_user, recipe, meal)

    copied = copy_service.copy_entry(user=active_user, entry=entry, day=TOMORROW)

    assert copied.recipe_id == recipe.id
    assert copied.entry_type == EntryType.RECIPE


def test_la_copie_conserve_lheure_et_change_la_date(active_user, recipe, meal):
    entry = journal(active_user, recipe, meal)

    copied = copy_service.copy_entry(user=active_user, entry=entry, day=TOMORROW)

    assert copied.consumed_at.date() == TOMORROW
    assert copied.consumed_at.hour == entry.consumed_at.hour


def test_une_recette_supprimee_fait_retomber_la_copie_sur_le_snapshot(active_user, recipe, meal):
    """Refuser ferait échouer la copie d'une journée pour une seule recette."""
    entry = journal(active_user, recipe, meal)
    recipe.deleted_at = timezone.now()
    recipe.save()

    copied = copy_service.copy_entry(user=active_user, entry=entry, day=TOMORROW)

    assert kcal(copied) == Decimal("400")
    assert copied.recipe_id is None


def test_copier_une_journee_melangee_respecte_chaque_nature(active_user, recipe, meal, chicken):
    """Aliment, recette et ajout rapide dans la même journée."""
    entries_service.create_food_entry(
        user=active_user,
        food=chicken,
        day=TODAY,
        meal_type=meal,
        quantity=Decimal("100"),
        unit_label="g",
        consumed_at=moment(TODAY, 8),
    )
    journal(active_user, recipe, meal, servings="1")
    entries_service.create_quick_add_entry(
        user=active_user,
        day=TODAY,
        meal_type=meal,
        consumed_at=moment(TODAY, 20),
        values={"name": "Restaurant", "energy_kcal": Decimal("500")},
    )

    # Les deux sources changent après coup.
    chicken.nutrition.energy_kcal = Decimal("300")
    chicken.nutrition.save()
    chicken.save()
    enrich(recipe, chicken)

    copy_service.copy_day(user=active_user, source_day=TODAY, target_days=[TOMORROW])

    copies = {
        entry.entry_type: entry for entry in DiaryEntry.objects.filter(diary_day__date=TOMORROW)
    }
    # L'aliment et la recette repartent des valeurs actuelles ; l'ajout rapide,
    # qui n'a pas de source, recopie son snapshot.
    assert kcal(copies[EntryType.FOOD]) == Decimal("300")
    assert kcal(copies[EntryType.RECIPE]) == Decimal("600")
    assert kcal(copies[EntryType.QUICK_ADD]) == Decimal("500")
