"""Duplication et copie d'entrées (spec 01 §5).

La règle décisive : une copie repart de la **version actuelle** de l'aliment,
alors que l'entrée d'origine garde son snapshot. L'implémentation naïve —
recopier la ligne — donnerait des valeurs périmées sans que rien ne le signale.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import User, UserStatus
from diary.models import DiaryEntry
from diary.services import copy as copy_service
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodPortion, FoodSource

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 26)
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def meal(active_user):
    return meal_types_for(active_user).first()


@pytest.fixture
def dinner(active_user):
    return meal_types_for(active_user).order_by("sort_order")[2]


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet rôti", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("192"))
    return food


def add(user, food, meal, quantity="150", unit="g", day=TODAY, hour=8) -> DiaryEntry:
    moment = timezone.make_aware(timezone.datetime(day.year, day.month, day.day, hour, 30))
    return entries_service.create_food_entry(
        user=user,
        food=food,
        day=day,
        meal_type=meal,
        quantity=Decimal(quantity),
        unit_label=unit,
        consumed_at=moment,
    )


# --- La règle : copier repart de la version actuelle ---------------------------


def test_la_copie_reprend_les_valeurs_actuelles_de_l_aliment(active_user, chicken, meal):
    """C'est tout l'enjeu : recopier la ligne donnerait des valeurs périmées."""
    original = add(active_user, chicken, meal)

    chicken.nutrition.energy_kcal = Decimal("500")
    chicken.nutrition.save()
    chicken.refresh_from_db()

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TODAY)

    assert copied.snapshot_energy_kcal == Decimal("500.000")


def test_l_original_garde_son_snapshot_apres_copie(active_user, chicken, meal):
    """L'autre moitié de la règle : l'historique ne bouge pas (spec 01 §6)."""
    original = add(active_user, chicken, meal)
    chicken.nutrition.energy_kcal = Decimal("500")
    chicken.nutrition.save()
    chicken.refresh_from_db()

    copy_service.copy_entry(user=active_user, entry=original, day=TODAY)
    original.refresh_from_db()

    assert original.snapshot_energy_kcal == Decimal("192.000")


def test_un_aliment_supprime_fait_retomber_sur_le_snapshot(active_user, chicken, meal):
    """Refuser ferait échouer la copie d'une journée pour un seul produit disparu."""
    original = add(active_user, chicken, meal)
    chicken.delete()
    original.refresh_from_db()

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TOMORROW)

    assert copied.snapshot_name == "Poulet rôti"
    assert copied.snapshot_energy_kcal == Decimal("192.000")
    assert copied.food is None


def test_un_aliment_devenu_invisible_fait_retomber_sur_le_snapshot(active_user, meal, db):
    """Un aliment partagé puis repassé en privé ne doit pas bloquer la copie."""
    other = User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )
    shared = Food.objects.create(
        source=FoodSource.USER, owner=other, name="Partagé", visibility="app_users"
    )
    FoodNutrition.objects.create(food=shared, energy_kcal=Decimal("300"))
    original = add(active_user, shared, meal)

    Food.objects.filter(pk=shared.pk).update(visibility="private")

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TOMORROW)

    assert copied.snapshot_energy_kcal == Decimal("300.000")


def test_un_ajout_rapide_se_duplique_tel_quel(active_user, meal):
    original = entries_service.create_quick_add_entry(
        user=active_user,
        day=TODAY,
        meal_type=meal,
        consumed_at=timezone.now(),
        values={"energy_kcal": Decimal("250")},
        note="Restaurant",
    )

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TOMORROW)

    assert copied.snapshot_energy_kcal == Decimal("250.000")
    assert copied.note == "Restaurant"


def test_une_portion_supprimee_ne_bloque_pas_la_copie(active_user, chicken, meal):
    """Le facteur figé prend le relais quand l'unité n'est plus calculable."""
    portion = FoodPortion.objects.create(
        food=chicken, name="1 blanc", gram_equivalent=Decimal("180")
    )
    original = add(active_user, chicken, meal, quantity="1", unit="1 blanc")
    portion.delete()

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TOMORROW)

    assert copied.snapshot_unit_factor == Decimal("180.0000")
    assert entries_service.computed_nutrition(copied)["energy_kcal"] == Decimal("345.600")


# --- Horaires et destination ---------------------------------------------------


def test_l_heure_est_conservee_seule_la_date_change(active_user, chicken, meal):
    """« horaires copiés » (spec 01 §5)."""
    original = add(active_user, chicken, meal, hour=7)

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TOMORROW)

    assert copied.diary_day.date == TOMORROW
    assert copied.consumed_at.hour == original.consumed_at.hour
    assert copied.consumed_at.minute == original.consumed_at.minute


def test_une_entree_peut_etre_dupliquee_vers_un_autre_repas(active_user, chicken, meal, dinner):
    original = add(active_user, chicken, meal)

    copied = copy_service.copy_entry(user=active_user, entry=original, day=TODAY, meal_type=dinner)

    assert copied.meal_type_id == dinner.id


# --- Copie de repas et de journée ----------------------------------------------


def test_copier_un_repas_vers_plusieurs_dates(active_user, chicken, meal):
    add(active_user, chicken, meal)
    add(active_user, chicken, meal, quantity="200")

    copied = copy_service.copy_meal(
        user=active_user,
        source_day=TODAY,
        source_meal_type=meal,
        target_days=[TOMORROW, TOMORROW + timedelta(days=1)],
    )

    assert len(copied) == 4
    assert DiaryEntry.objects.filter(diary_day__date=TOMORROW).count() == 2


def test_copier_un_repas_vers_un_autre_repas(active_user, chicken, meal, dinner):
    add(active_user, chicken, meal)

    copy_service.copy_meal(
        user=active_user,
        source_day=TODAY,
        source_meal_type=meal,
        target_days=[TOMORROW],
        target_meal_type=dinner,
    )

    assert DiaryEntry.objects.filter(diary_day__date=TOMORROW, meal_type=dinner).count() == 1


def test_copier_une_journee_replace_chaque_entree_dans_son_repas(
    active_user, chicken, meal, dinner
):
    add(active_user, chicken, meal)
    add(active_user, chicken, dinner, quantity="200")

    copy_service.copy_day(user=active_user, source_day=TODAY, target_days=[TOMORROW])

    copied = DiaryEntry.objects.filter(diary_day__date=TOMORROW)
    assert copied.count() == 2
    assert copied.filter(meal_type=dinner).count() == 1


def test_une_copie_s_ajoute_et_n_ecrase_rien(active_user, chicken, meal):
    """La journée cible garde ce qu'elle contenait."""
    add(active_user, chicken, meal)
    add(active_user, chicken, meal, quantity="90", day=TOMORROW)

    copy_service.copy_day(user=active_user, source_day=TODAY, target_days=[TOMORROW])

    assert DiaryEntry.objects.filter(diary_day__date=TOMORROW).count() == 2


def test_copier_une_journee_vide_ne_fait_rien(active_user):
    copied = copy_service.copy_day(user=active_user, source_day=TODAY, target_days=[TOMORROW])

    assert copied == []
    assert not DiaryEntry.objects.exists()


# --- Ajout sur plusieurs dates -------------------------------------------------


def test_un_aliment_peut_etre_ajoute_sur_plusieurs_dates(active_user, chicken, meal):
    days = [TODAY, TOMORROW, TOMORROW + timedelta(days=1)]

    copied = copy_service.add_food_on_days(
        user=active_user,
        food=chicken,
        days=days,
        meal_type=meal,
        quantity=Decimal("100"),
        unit_label="g",
        consumed_at=timezone.now(),
    )

    assert len(copied) == 3
    assert {entry.diary_day.date for entry in copied} == set(days)


def test_l_ajout_multiple_alimente_les_recents(active_user, chicken, meal):
    from nutrition.models import UserFoodHistory

    copy_service.add_food_on_days(
        user=active_user,
        food=chicken,
        days=[TODAY, TOMORROW],
        meal_type=meal,
        quantity=Decimal("100"),
        unit_label="g",
        consumed_at=timezone.now(),
    )

    assert UserFoodHistory.objects.get(user=active_user, food=chicken).use_count == 2
