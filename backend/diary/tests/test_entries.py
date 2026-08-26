"""Snapshots et calcul des entrées (spec 01 §5, §6, §8 et §12).

Le snapshot est la donnée historique de vérité : ces tests vérifient qu'une
entrée survit à la modification comme à la disparition de sa source, et qu'elle
reste recalculable depuis elle seule.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from diary.models import DiaryEntry, EntryType
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodPortion, FoodSource, UnitType, UserFoodHistory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)


@pytest.fixture
def meal(active_user):
    return meal_types_for(active_user).first()


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="1",
        name="Poulet rôti",
        reference_amount=100,
        reference_unit=UnitType.GRAM,
    )
    FoodNutrition.objects.create(
        food=food,
        energy_kcal=Decimal("192"),
        protein_g=Decimal("17.3"),
        fat_g=Decimal("13.5"),
        # Fibres volontairement inconnues.
    )
    return food


def add(user, food, meal, quantity="150", unit="g", day=TODAY) -> DiaryEntry:
    return entries_service.create_food_entry(
        user=user,
        food=food,
        day=day,
        meal_type=meal,
        quantity=Decimal(quantity),
        unit_label=unit,
        consumed_at=timezone.now(),
    )


# --- Snapshot ----------------------------------------------------------------


def test_le_snapshot_porte_les_valeurs_de_reference_pas_les_valeurs_consommees(
    active_user, chicken, meal
):
    """C'est ce qui rend l'entrée recalculable sans sa source."""
    entry = add(active_user, chicken, meal, quantity="150")

    assert entry.snapshot_energy_kcal == Decimal("192.000")
    assert entry.snapshot_reference_amount == 100
    assert entry.quantity == Decimal("150.000")


def test_les_valeurs_consommees_sont_calculees(active_user, chicken, meal):
    entry = add(active_user, chicken, meal, quantity="150")

    computed = entries_service.computed_nutrition(entry)

    assert computed["energy_kcal"] == Decimal("288.000")
    assert computed["protein_g"] == Decimal("25.950")


def test_une_valeur_inconnue_le_reste_apres_multiplication(active_user, chicken, meal):
    """Multiplier une inconnue ne la transforme pas en zéro (spec 01 §8)."""
    entry = add(active_user, chicken, meal)

    assert entries_service.computed_nutrition(entry)["fiber_g"] is None


def test_modifier_l_aliment_ne_change_pas_l_entree(active_user, chicken, meal):
    """Une modification de la source ne touche jamais l'historique (spec 01 §6)."""
    entry = add(active_user, chicken, meal)

    chicken.nutrition.energy_kcal = Decimal("500")
    chicken.nutrition.save()
    entry.refresh_from_db()

    assert entry.snapshot_energy_kcal == Decimal("192.000")


def test_un_nouvel_ajout_reprend_les_nouvelles_valeurs(active_user, chicken, meal):
    """L'inverse doit être vrai : une copie repart de la version actuelle."""
    add(active_user, chicken, meal)
    chicken.nutrition.energy_kcal = Decimal("500")
    chicken.nutrition.save()
    chicken.refresh_from_db()

    second = add(active_user, chicken, meal)

    assert second.snapshot_energy_kcal == Decimal("500.000")


def test_supprimer_l_aliment_ne_supprime_pas_l_entree(active_user, chicken, meal):
    """`SET_NULL` : l'historique de qui a consommé ne dépend pas de la source."""
    entry = add(active_user, chicken, meal)

    chicken.delete()
    entry.refresh_from_db()

    assert entry.food is None
    assert entry.snapshot_name == "Poulet rôti"
    assert entries_service.computed_nutrition(entry)["energy_kcal"] == Decimal("288.000")


def test_une_entree_reste_recalculable_sans_son_aliment(active_user, chicken, meal):
    """Modifier la quantité d'une vieille entrée ne doit rien exiger de la source."""
    entry = add(active_user, chicken, meal, quantity="100")
    chicken.delete()
    entry.refresh_from_db()

    entry.quantity = Decimal("200")
    entry.save()

    assert entries_service.computed_nutrition(entry)["energy_kcal"] == Decimal("384.000")


def test_le_facteur_d_unite_est_fige_a_l_ajout(active_user, chicken, meal):
    """Une portion supprimée ne doit pas rendre l'entrée incalculable."""
    portion = FoodPortion.objects.create(
        food=chicken, name="1 blanc", gram_equivalent=Decimal("180")
    )
    entry = add(active_user, chicken, meal, quantity="1", unit="1 blanc")

    portion.delete()
    entry.refresh_from_db()

    assert entry.snapshot_unit_factor == Decimal("180.0000")
    assert entries_service.computed_nutrition(entry)["energy_kcal"] == Decimal("345.600")


# --- Usage -------------------------------------------------------------------


def test_journaliser_alimente_les_recents_et_les_frequents(active_user, chicken, meal):
    """Sans cet appel, les listes de la page Aliments resteraient vides."""
    add(active_user, chicken, meal)
    add(active_user, chicken, meal)

    history = UserFoodHistory.objects.get(user=active_user, food=chicken)

    assert history.use_count == 2
    assert history.last_used_at is not None


# --- Ajout rapide ------------------------------------------------------------


def test_un_ajout_rapide_accepte_les_calories_seules(active_user, meal):
    entry = entries_service.create_quick_add_entry(
        user=active_user,
        day=TODAY,
        meal_type=meal,
        consumed_at=timezone.now(),
        values={"energy_kcal": Decimal("250")},
    )

    assert entry.entry_type == EntryType.QUICK_ADD
    assert entries_service.computed_nutrition(entry)["energy_kcal"] == Decimal("250.000")
    assert entries_service.computed_nutrition(entry)["fiber_g"] is None


def test_un_ajout_rapide_accepte_les_macros(active_user, meal):
    entry = entries_service.create_quick_add_entry(
        user=active_user,
        day=TODAY,
        meal_type=meal,
        consumed_at=timezone.now(),
        values={
            "energy_kcal": Decimal("250"),
            "protein_g": Decimal("20"),
            "carbohydrates_g": Decimal("10"),
            "fat_g": Decimal("14"),
        },
        note="Restaurant",
    )

    computed = entries_service.computed_nutrition(entry)

    assert computed["protein_g"] == Decimal("20.000")
    assert entry.note == "Restaurant"


# --- Totaux ------------------------------------------------------------------


def test_les_totaux_additionnent_les_entrees(active_user, chicken, meal):
    add(active_user, chicken, meal, quantity="100")
    add(active_user, chicken, meal, quantity="200")

    totals, _ = entries_service.sum_nutrition(DiaryEntry.objects.all())

    assert totals["energy_kcal"] == Decimal("576.000")


def test_un_nutriment_inconnu_partout_reste_inconnu(active_user, chicken, meal):
    add(active_user, chicken, meal)

    totals, incomplete = entries_service.sum_nutrition(DiaryEntry.objects.all())

    assert totals["fiber_g"] is None
    # Rien à signaler : aucune valeur partielle n'est affichée.
    assert "fiber_g" not in incomplete


def test_un_total_partiel_est_signale(active_user, chicken, meal):
    """Additionner en ignorant une inconnue reviendrait à la compter pour zéro."""
    other = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="9", name="Lentilles", reference_amount=100
    )
    FoodNutrition.objects.create(food=other, energy_kcal=Decimal("100"), fiber_g=Decimal("8"))

    add(active_user, chicken, meal)  # fibres inconnues
    add(active_user, other, meal, quantity="100")

    totals, incomplete = entries_service.sum_nutrition(DiaryEntry.objects.all())

    assert totals["fiber_g"] == Decimal("8.000")
    assert "fiber_g" in incomplete


def test_une_journee_vide_vaut_zero_et_non_inconnu(active_user):
    """Rien de consommé se sait : c'est zéro, pas une donnée manquante."""
    totals, incomplete = entries_service.sum_nutrition([])

    assert totals["energy_kcal"] == Decimal(0)
    assert incomplete == []


# --- Journée -----------------------------------------------------------------


def test_le_journal_accepte_le_passe_et_le_futur(active_user, chicken, meal):
    """Le journal est modifiable dans les trois temps (spec 01 §5)."""
    hier = TODAY - timedelta(days=1)
    demain = TODAY + timedelta(days=1)

    add(active_user, chicken, meal, day=hier)
    add(active_user, chicken, meal, day=demain)

    assert DiaryEntry.objects.filter(diary_day__date=hier).exists()
    assert DiaryEntry.objects.filter(diary_day__date=demain).exists()
