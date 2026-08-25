"""Cycle de vie des objectifs nutritionnels (spec 01 §4)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from nutrition.models import NutritionGoal
from nutrition.services import goals as goals_service

pytestmark = pytest.mark.django_db

BASE_VALUES = {
    "daily_calories": Decimal("2000"),
    "protein_g": Decimal("150"),
    "carbs_g": Decimal("200"),
    "fat_g": Decimal("67"),
}


def test_creation_dun_premier_objectif(active_user):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    assert goal.start_date == date(2026, 1, 1)
    assert goal.end_date is None
    assert goal.is_current is True


def test_un_nouvel_objectif_cloture_le_precedent_la_veille(active_user):
    ancien = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    goals_service.create_goal(
        active_user,
        start_date=date(2026, 3, 1),
        **{**BASE_VALUES, "daily_calories": Decimal("1800")},
    )

    ancien.refresh_from_db()
    assert ancien.end_date == date(2026, 2, 28)
    assert ancien.is_current is False


def test_le_changement_nest_pas_retroactif(active_user):
    """L'objectif passé garde ses valeurs d'origine (spec 01 §4)."""
    ancien = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    goals_service.create_goal(
        active_user,
        start_date=date(2026, 3, 1),
        **{**BASE_VALUES, "daily_calories": Decimal("1500")},
    )

    ancien.refresh_from_db()
    assert ancien.daily_calories == Decimal("2000.00")


def test_lhistorique_est_conserve(active_user):
    goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    goals_service.create_goal(active_user, start_date=date(2026, 2, 1), **BASE_VALUES)
    goals_service.create_goal(active_user, start_date=date(2026, 3, 1), **BASE_VALUES)

    assert NutritionGoal.objects.filter(user=active_user).count() == 3


def test_un_objectif_recree_le_meme_jour_est_mis_a_jour(active_user):
    """Un objectif du jour n'a couvert aucune journée close : il est remplacé."""
    premier = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    second = goals_service.create_goal(
        active_user,
        start_date=date(2026, 1, 1),
        **{**BASE_VALUES, "daily_calories": Decimal("1700")},
    )

    assert second.pk == premier.pk
    assert NutritionGoal.objects.filter(user=active_user).count() == 1
    assert second.daily_calories == Decimal("1700")


def test_une_seule_periode_ouverte_a_la_fois(active_user):
    goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    goals_service.create_goal(active_user, start_date=date(2026, 2, 1), **BASE_VALUES)

    assert NutritionGoal.objects.filter(user=active_user, end_date__isnull=True).count() == 1


def test_la_base_refuse_deux_periodes_ouvertes(active_user):
    goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    with pytest.raises(IntegrityError):
        NutritionGoal.objects.create(user=active_user, start_date=date(2026, 5, 1), **BASE_VALUES)


def test_la_base_refuse_une_fin_avant_le_debut(active_user):
    goal = NutritionGoal(
        user=active_user, start_date=date(2026, 2, 1), end_date=date(2026, 1, 1), **BASE_VALUES
    )

    with pytest.raises(ValidationError):
        goal.full_clean()


# --- Résolution ---------------------------------------------------------------


def test_objectif_courant(active_user):
    goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    recent = goals_service.create_goal(active_user, start_date=date(2026, 3, 1), **BASE_VALUES)

    assert goals_service.current_goal(active_user, date(2026, 6, 1)) == recent


def test_objectif_applicable_a_une_date_passee(active_user):
    ancien = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    goals_service.create_goal(active_user, start_date=date(2026, 3, 1), **BASE_VALUES)

    assert goals_service.current_goal(active_user, date(2026, 2, 15)) == ancien


def test_aucun_objectif_avant_la_premiere_periode(active_user):
    goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    assert goals_service.current_goal(active_user, date(2025, 12, 31)) is None


def test_aucun_objectif_du_tout(active_user):
    assert goals_service.current_goal(active_user) is None
    assert goals_service.resolve_for_date(active_user, date.today()) is None


# --- Surcharges par jour de semaine -------------------------------------------


def test_une_surcharge_remplace_les_valeurs_du_jour(active_user):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    # 2026-01-05 est un lundi.
    goals_service.set_day_override(goal, 0, daily_calories=Decimal("2500"))

    resolved = goals_service.resolve_for_date(active_user, date(2026, 1, 5))

    assert resolved["weekday"] == 0
    assert resolved["daily_calories"] == Decimal("2500")
    # Les champs non surchargés gardent la valeur de base.
    assert resolved["protein_g"] == Decimal("150.00")


def test_une_surcharge_ne_sapplique_quau_bon_jour(active_user):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    goals_service.set_day_override(goal, 0, daily_calories=Decimal("2500"))

    mardi = goals_service.resolve_for_date(active_user, date(2026, 1, 6))

    assert mardi["daily_calories"] == Decimal("2000.00")


def test_une_surcharge_desactivee_est_ignoree(active_user):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)
    goals_service.set_day_override(goal, 0, daily_calories=Decimal("2500"), enabled=False)

    resolved = goals_service.resolve_for_date(active_user, date(2026, 1, 5))

    assert resolved["daily_calories"] == Decimal("2000.00")


def test_une_surcharge_par_jour_est_unique(active_user):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    goals_service.set_day_override(goal, 3, daily_calories=Decimal("2100"))
    goals_service.set_day_override(goal, 3, daily_calories=Decimal("2300"))

    assert goal.day_overrides.count() == 1
    assert goal.day_overrides.get().daily_calories == Decimal("2300")


@pytest.mark.parametrize("weekday", [-1, 7])
def test_un_jour_hors_plage_est_refuse(active_user, weekday):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **BASE_VALUES)

    with pytest.raises((ValidationError, IntegrityError, ValueError)):
        goals_service.set_day_override(goal, weekday, daily_calories=Decimal("2100"))


# --- Cohérence macros / calories ----------------------------------------------


def test_lecart_entre_macros_et_calories_est_signale(active_user):
    """Les calories font foi : l'écart est mesuré, jamais corrigé (spec 01 §4)."""
    gap = goals_service.macro_calorie_gap(
        {
            "daily_calories": Decimal("2000"),
            "protein_g": Decimal("150"),
            "carbs_g": Decimal("200"),
            "fat_g": Decimal("100"),
        }
    )

    # 150*4 + 200*4 + 100*9 = 2300 kcal, soit 300 de trop.
    assert gap == Decimal("300")


def test_aucun_ecart_pour_des_macros_coherentes(active_user):
    gap = goals_service.macro_calorie_gap(
        {
            # 150*4 + 200*4 + 11*9 = 1499 kcal
            "daily_calories": Decimal("1499"),
            "protein_g": Decimal("150"),
            "carbs_g": Decimal("200"),
            "fat_g": Decimal("11"),
        }
    )

    assert gap == Decimal("0")


# --- Glucides nets ------------------------------------------------------------


def test_glucides_nets(active_user):
    goal = goals_service.create_goal(
        active_user, start_date=date.today(), **{**BASE_VALUES, "fiber_g": Decimal("30")}
    )

    assert goal.net_carbs_g == Decimal("170.00")


def test_glucides_nets_inconnus_sans_fibres(active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **BASE_VALUES)

    # Valeur inconnue : jamais artificiellement 0 (spec 01 §8).
    assert goal.net_carbs_g is None


def test_la_veille_est_bien_calculee_sur_un_changement_de_mois(active_user):
    ancien = goals_service.create_goal(active_user, start_date=date(2026, 1, 15), **BASE_VALUES)
    nouveau_debut = date(2026, 1, 15) + timedelta(days=45)

    goals_service.create_goal(active_user, start_date=nouveau_debut, **BASE_VALUES)

    ancien.refresh_from_db()
    assert ancien.end_date == nouveau_debut - timedelta(days=1)
