"""Rapports de période (spec 01 §22, spec 04 §17).

Un rapport assemble ce que d'autres services calculent. Ces tests vérifient
qu'il n'en trahit aucune règle en chemin : le dénominateur reste les journées
tenues, l'objectif retenu est celui de chaque date, et une valeur inconnue
sort vide plutôt qu'à zéro.
"""

import csv
import io
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from diary.services import entries as entries_service
from diary.services import reports
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from nutrition.services.goals import create_goal, set_day_override
from progress.models import WeightEntry

pytestmark = pytest.mark.django_db

MONDAY = date(2026, 8, 31)
SUNDAY = MONDAY + timedelta(days=6)


@pytest.fixture
def meal(active_user):
    return meal_types_for(active_user).first()


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="r1", name="Poulet rôti", reference_amount=100
    )
    FoodNutrition.objects.create(
        food=food,
        energy_kcal=Decimal("200"),
        protein_g=Decimal("20"),
        # Fibres volontairement inconnues.
    )
    return food


@pytest.fixture
def goal(active_user):
    return create_goal(
        user=active_user,
        daily_calories=Decimal("2000"),
        protein_g=Decimal("100"),
        carbs_g=Decimal("200"),
        fat_g=Decimal("70"),
        start_date=MONDAY - timedelta(days=7),
    )


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


class TestReportComposition:
    def test_seules_les_journees_tenues_font_des_lignes(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)
        log(active_user, meal, chicken, MONDAY + timedelta(days=3))

        report = reports.build(active_user, MONDAY, SUNDAY)

        assert report.logged_days == 2
        assert report.calendar_days == 7
        assert [row.date for row in report.days] == [MONDAY, MONDAY + timedelta(days=3)]

    def test_la_moyenne_ne_divise_pas_par_le_calendrier(self, active_user, meal, chicken):
        for offset in range(2):
            log(active_user, meal, chicken, MONDAY + timedelta(days=offset))

        report = reports.build(active_user, MONDAY, SUNDAY)

        assert report.averages["energy_kcal"] == Decimal("200")

    def test_l_objectif_de_chaque_ligne_est_celui_de_sa_date(
        self, active_user, meal, chicken, goal
    ):
        set_day_override(goal, MONDAY.weekday(), daily_calories=Decimal("1500"))
        log(active_user, meal, chicken, MONDAY)
        log(active_user, meal, chicken, MONDAY + timedelta(days=1))

        report = reports.build(active_user, MONDAY, SUNDAY)

        assert report.days[0].target_calories == Decimal("1500")
        assert report.days[1].target_calories == Decimal("2000")

    def test_la_variation_de_poids_reprend_la_serie_de_progression(
        self, active_user, meal, chicken
    ):
        log(active_user, meal, chicken, MONDAY)
        WeightEntry.objects.create(user=active_user, date=MONDAY, weight_kg=Decimal("80"))
        WeightEntry.objects.create(user=active_user, date=SUNDAY, weight_kg=Decimal("78.5"))

        report = reports.build(active_user, MONDAY, SUNDAY)

        assert report.weight_change == Decimal("-1.5")

    def test_une_seule_pesee_ne_fait_pas_une_variation(self, active_user):
        WeightEntry.objects.create(user=active_user, date=MONDAY, weight_kg=Decimal("80"))

        assert reports.build(active_user, MONDAY, SUNDAY).weight_change is None

    def test_une_periode_vide_ne_fabrique_rien(self, active_user):
        report = reports.build(active_user, MONDAY, SUNDAY)

        assert report.days == []
        assert report.averages["energy_kcal"] is None
        assert report.weight_change is None


class TestCsv:
    def rows(self, report) -> list[list[str]]:
        return list(csv.reader(io.StringIO(reports.to_csv(report))))

    def test_l_entete_est_stable(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        header = self.rows(reports.build(active_user, MONDAY, SUNDAY))[0]

        assert header[:4] == ["date", "entrées", "objectif_kcal", "poids_kg"]
        assert header[4] == "energy_kcal"
        assert len(header) == 4 + len(reports.CSV_NUTRIENTS)

    def test_une_valeur_inconnue_sort_vide_et_non_zero(self, active_user, meal, chicken):
        """Le poulet ne déclare pas ses fibres : la cellule reste vide."""
        log(active_user, meal, chicken, MONDAY)

        rows = self.rows(reports.build(active_user, MONDAY, SUNDAY))
        colonne = rows[0].index("fiber_g")

        assert rows[1][colonne] == ""

    def test_les_decimales_ne_sont_pas_localisees(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY, quantity="50")  # 100 kcal, 10 g de protéines

        rows = self.rows(reports.build(active_user, MONDAY, SUNDAY))
        colonne = rows[0].index("protein_g")

        assert rows[1][colonne] == "10.00"
        assert "," not in rows[1][colonne]

    def test_une_journee_non_tenue_n_a_pas_de_ligne(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        assert len(self.rows(reports.build(active_user, MONDAY, SUNDAY))) == 2

    def test_une_periode_vide_garde_son_entete(self, active_user):
        rows = self.rows(reports.build(active_user, MONDAY, SUNDAY))

        assert len(rows) == 1


class TestPdf:
    def test_le_fichier_est_un_pdf(self, active_user, meal, chicken, goal):
        log(active_user, meal, chicken, MONDAY, quantity="1000")

        contenu = reports.to_pdf(reports.build(active_user, MONDAY, SUNDAY))

        assert contenu.startswith(b"%PDF")
        assert contenu.rstrip().endswith(b"%%EOF")

    def test_la_periode_et_les_accents_y_figurent(self, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        contenu = reports.to_pdf(reports.build(active_user, MONDAY, SUNDAY))

        # Le titre du document est lisible sans décompresser les flux.
        assert "31/08/2026".encode("utf-16-be") in contenu or b"31/08/2026" in contenu

    def test_une_periode_vide_produit_quand_meme_un_pdf(self, active_user):
        """Un rapport vide est une réponse ; une exception n'en est pas une."""
        contenu = reports.to_pdf(reports.build(active_user, MONDAY, SUNDAY))

        assert contenu.startswith(b"%PDF")

    def test_quatre_vingt_dix_jours_restent_synchrones(self, active_user, meal, chicken):
        """La mesure décide, pas l'intuition (spec 04 §17).

        Au-delà de quelques secondes, l'export devrait passer par le socle
        asynchrone de l'étape 12. Ce test échouera le jour où ce sera le cas.
        """
        start = MONDAY - timedelta(days=89)
        for offset in range(90):
            log(active_user, meal, chicken, start + timedelta(days=offset))
            WeightEntry.objects.create(
                user=active_user,
                date=start + timedelta(days=offset),
                weight_kg=Decimal("80") - Decimal(offset) / 100,
            )

        report = reports.build(active_user, start, MONDAY)

        début = time.perf_counter()
        contenu = reports.to_pdf(report)
        durée = time.perf_counter() - début

        assert contenu.startswith(b"%PDF")
        assert durée < 2.0, f"{durée:.2f} s : l'export mérite de passer en asynchrone"
