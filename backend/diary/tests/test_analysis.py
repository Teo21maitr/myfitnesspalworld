"""Analyse du journal sur une période (spec 01 §21-22).

Le premier bloc protège la règle de l'étape : **une journée sans entrée n'est
pas une journée à zéro**. Diviser par sept une semaine tenue cinq jours donne
un chiffre plausible et faux, et rien à l'écran ne le trahirait.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from diary.services import analysis
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from nutrition.services.goals import create_goal, set_day_override

pytestmark = pytest.mark.django_db

MONDAY = date(2026, 8, 31)
SUNDAY = MONDAY + timedelta(days=6)


@pytest.fixture
def meal(active_user):
    return meal_types_for(active_user).first()


@pytest.fixture
def other_user(db):
    from accounts.models import User, UserStatus

    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="a1", name="Poulet rôti", reference_amount=100
    )
    FoodNutrition.objects.create(
        food=food,
        energy_kcal=Decimal("200"),
        protein_g=Decimal("20"),
        # Fibres volontairement inconnues : ce produit ne les déclare pas.
    )
    return food


@pytest.fixture
def rice(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="a2", name="Riz", reference_amount=100
    )
    FoodNutrition.objects.create(
        food=food, energy_kcal=Decimal("130"), protein_g=Decimal("3"), fiber_g=Decimal("0.4")
    )
    return food


def log(user, meal, food, day, quantity="100"):
    return entries_service.create_food_entry(
        user=user,
        food=food,
        day=day,
        meal_type=meal,
        quantity=Decimal(quantity),
        unit_label="g",
        consumed_at=timezone.make_aware(datetime.combine(day, datetime.min.time())),
    )


class TestAnUnloggedDayIsNotAZeroDay:
    """Le piège : la moyenne porte sur les journées tenues, pas sur le calendrier."""

    def test_la_moyenne_porte_sur_les_journees_tenues(self, active_user, meal, chicken):
        # Cinq journées à 200 kcal, deux non journalisées.
        for offset in range(5):
            log(active_user, meal, chicken, MONDAY + timedelta(days=offset))

        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)
        moyennes = analysis.averages(daily, ("energy_kcal",))

        # 200, et non 1000/7 = 143.
        assert moyennes["energy_kcal"] == Decimal("200")

    def test_le_nombre_de_journees_tenues_est_rendu(self, active_user, meal, chicken):
        for offset in range(5):
            log(active_user, meal, chicken, MONDAY + timedelta(days=offset))

        assert len(analysis.logged_days(active_user, MONDAY, SUNDAY)) == 5

    def test_une_journee_vide_n_entre_pas_dans_les_totaux(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)

        assert list(daily) == [MONDAY]

    def test_une_periode_vide_ne_renvoie_pas_des_zeros(self, active_user, meal):
        """Ne rien savoir n'est pas savoir que c'est zéro."""
        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)
        moyennes = analysis.averages(daily, ("energy_kcal",))

        assert daily == {}
        assert moyennes["energy_kcal"] is None


class TestPartialTotals:
    def test_un_nutriment_non_renseigne_rend_le_total_partiel(self, active_user, meal, chicken):
        """Le poulet ne déclare pas ses fibres : ce n'est pas qu'il n'en a pas."""
        log(active_user, meal, chicken, MONDAY)

        resultat = analysis.nutrient_sources(
            active_user, nutrient="fiber_g", start=MONDAY, end=SUNDAY
        )

        assert resultat.is_partial
        assert resultat.unknown_entries == 1
        assert resultat.total is None

    def test_les_parts_sont_calculees_sur_le_connu(self, active_user, meal, chicken, rice):
        log(active_user, meal, chicken, MONDAY)
        log(active_user, meal, rice, MONDAY)

        resultat = analysis.nutrient_sources(
            active_user, nutrient="fiber_g", start=MONDAY, end=SUNDAY
        )

        # Seul le riz renseigne les fibres : il en fait 100 % du connu, mais
        # l'analyse reste marquée partielle.
        assert resultat.is_partial
        assert resultat.sources[0].name == "Riz"
        assert resultat.sources[0].share == pytest.approx(100)

    def test_un_total_complet_n_est_pas_marque_partiel(self, active_user, meal, rice):
        log(active_user, meal, rice, MONDAY)

        resultat = analysis.nutrient_sources(
            active_user, nutrient="fiber_g", start=MONDAY, end=SUNDAY
        )

        assert not resultat.is_partial


class TestSources:
    def test_le_classement_suit_les_quantites_apportees(self, active_user, meal, chicken, rice):
        log(active_user, meal, chicken, MONDAY)  # 20 g de protéines
        log(active_user, meal, rice, MONDAY)  # 3 g

        resultat = analysis.nutrient_sources(
            active_user, nutrient="protein_g", start=MONDAY, end=SUNDAY
        )

        assert [source.name for source in resultat.sources] == ["Poulet rôti", "Riz"]
        assert resultat.sources[0].total == Decimal("20")

    def test_deux_entrees_du_meme_aliment_se_cumulent(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)
        log(active_user, meal, chicken, MONDAY + timedelta(days=1))

        resultat = analysis.nutrient_sources(
            active_user, nutrient="protein_g", start=MONDAY, end=SUNDAY
        )

        assert len(resultat.sources) == 1
        assert resultat.sources[0].entries == 2
        assert resultat.sources[0].total == Decimal("40")

    def test_un_aliment_supprime_garde_son_nom(self, active_user, meal, chicken):
        """Le snapshot est la donnée historique de vérité (spec 01 §6)."""
        log(active_user, meal, chicken, MONDAY)
        chicken.delete()

        resultat = analysis.nutrient_sources(
            active_user, nutrient="protein_g", start=MONDAY, end=SUNDAY
        )

        assert resultat.sources[0].name == "Poulet rôti"

    def test_les_entrees_d_un_autre_compte_ne_sont_jamais_agregees(
        self, active_user, other_user, meal, chicken
    ):
        autre_repas = meal_types_for(other_user).first()
        log(other_user, autre_repas, chicken, MONDAY, quantity="500")
        log(active_user, meal, chicken, MONDAY)

        resultat = analysis.nutrient_sources(
            active_user, nutrient="protein_g", start=MONDAY, end=SUNDAY
        )

        assert resultat.sources[0].total == Decimal("20")

    def test_une_periode_ne_deborde_pas_de_ses_bornes(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY - timedelta(days=1))
        log(active_user, meal, chicken, SUNDAY + timedelta(days=1))

        resultat = analysis.nutrient_sources(
            active_user, nutrient="protein_g", start=MONDAY, end=SUNDAY
        )

        assert resultat.sources == []


class TestGoalAdherence:
    @pytest.fixture
    def goal(self, active_user):
        return create_goal(
            user=active_user,
            daily_calories=Decimal("2000"),
            protein_g=Decimal("100"),
            carbs_g=Decimal("200"),
            fat_g=Decimal("70"),
            start_date=MONDAY - timedelta(days=7),
        )

    def test_une_journee_dans_la_tolerance_est_comptee(self, active_user, meal, chicken, goal):
        log(active_user, meal, chicken, MONDAY, quantity="1000")  # 2000 kcal

        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)
        respect = analysis.goal_adherence(active_user, daily)

        assert respect == {"days_measured": 1, "days_within_goal": 1}

    def test_une_journee_hors_tolerance_est_comptee_mais_pas_retenue(
        self, active_user, meal, chicken, goal
    ):
        log(active_user, meal, chicken, MONDAY, quantity="100")  # 200 kcal

        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)

        assert analysis.goal_adherence(active_user, daily) == {
            "days_measured": 1,
            "days_within_goal": 0,
        }

    def test_l_objectif_retenu_est_celui_de_la_date(self, active_user, meal, chicken, goal):
        """Un objectif du dimanche ne juge pas un lundi (spec 01 §4)."""
        # Le lundi vise 1000 kcal au lieu de 2000.
        set_day_override(goal, MONDAY.weekday(), daily_calories=Decimal("1000"))
        log(active_user, meal, chicken, MONDAY, quantity="500")  # 1000 kcal

        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)

        assert analysis.goal_adherence(active_user, daily)["days_within_goal"] == 1

    def test_sans_objectif_rien_n_est_mesure(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        daily = analysis.daily_totals(active_user, MONDAY, SUNDAY)

        assert analysis.goal_adherence(active_user, daily)["days_measured"] == 0
