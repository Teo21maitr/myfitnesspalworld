"""Endpoints d'analyse et de rapports (spec 04 §17-18).

Ce que ces tests protègent, au-delà des formes de réponse : le nombre de
journées tenues accompagne toujours les moyennes, un total partiel est annoncé
comme tel, et les données d'un autre compte ne sont jamais agrégées.
"""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from nutrition.services.goals import create_goal
from progress.models import WeightEntry

pytestmark = pytest.mark.django_db

MONDAY = date(2026, 8, 31)
SUNDAY = MONDAY + timedelta(days=6)
PERIOD = {"from": MONDAY.isoformat(), "to": SUNDAY.isoformat()}


@pytest.fixture
def meal(active_user):
    return meal_types_for(active_user).first()


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="p1", name="Poulet rôti", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"), protein_g=Decimal("20"))
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


def client_for(user: User) -> APIClient:
    from django.conf import settings

    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


class TestFoodAnalysis:
    def test_les_sources_sont_classees(self, auth_client, active_user, meal, chicken):
        riz = Food.objects.create(source=FoodSource.CIQUAL, external_id="r9", name="Riz")
        FoodNutrition.objects.create(food=riz, energy_kcal=Decimal("130"), protein_g=Decimal("3"))
        log(active_user, meal, chicken, MONDAY)
        log(active_user, meal, riz, MONDAY)

        response = auth_client.get("/api/v1/analysis/food/", {**PERIOD, "nutrient": "protein_g"})

        assert response.status_code == 200
        assert [source["name"] for source in response.data["sources"]] == ["Poulet rôti", "Riz"]
        assert response.data["label"] == "Protéines (g)"

    def test_un_total_partiel_est_annonce(self, auth_client, active_user, meal, chicken):
        """Le poulet ne renseigne pas ses fibres : l'écran doit le savoir."""
        log(active_user, meal, chicken, MONDAY)

        response = auth_client.get("/api/v1/analysis/food/", {**PERIOD, "nutrient": "fiber_g"})

        assert response.data["is_partial"] is True
        assert response.data["unknown_entries"] == 1

    def test_le_nombre_de_journees_tenues_accompagne_la_periode(
        self, auth_client, active_user, meal, chicken
    ):
        log(active_user, meal, chicken, MONDAY)
        log(active_user, meal, chicken, MONDAY + timedelta(days=2))

        response = auth_client.get("/api/v1/analysis/food/", PERIOD)

        assert response.data["logged_days"] == 2
        assert response.data["from"] == MONDAY.isoformat()

    def test_un_nutriment_inconnu_est_refuse(self, auth_client):
        response = auth_client.get("/api/v1/analysis/food/", {**PERIOD, "nutrient": "zorglub"})

        assert response.status_code == 400
        assert "nutrient" in response.data["errors"]

    def test_une_periode_trop_longue_est_refusee(self, auth_client):
        response = auth_client.get(
            "/api/v1/analysis/food/",
            {"from": "2020-01-01", "to": MONDAY.isoformat()},
        )

        assert response.status_code == 400


class TestWeeklyAnalysis:
    def test_la_moyenne_porte_sur_les_journees_tenues(
        self, auth_client, active_user, meal, chicken
    ):
        for offset in range(5):
            log(active_user, meal, chicken, MONDAY + timedelta(days=offset))

        response = auth_client.get("/api/v1/analysis/weekly/", {"from": MONDAY.isoformat()})

        assert response.status_code == 200
        assert response.data["logged_days"] == 5
        assert response.data["calendar_days"] == 7
        # 200 kcal, et non 1000/7.
        assert Decimal(response.data["averages"]["energy_kcal"]) == Decimal("200.00")

    def test_la_semaine_couvre_sept_jours(self, auth_client):
        response = auth_client.get("/api/v1/analysis/weekly/", {"from": MONDAY.isoformat()})

        assert response.data["from"] == MONDAY.isoformat()
        assert response.data["to"] == SUNDAY.isoformat()

    def test_le_respect_des_objectifs_est_renvoye(self, auth_client, active_user, meal, chicken):
        create_goal(
            user=active_user,
            daily_calories=Decimal("2000"),
            protein_g=Decimal("100"),
            carbs_g=Decimal("200"),
            fat_g=Decimal("70"),
            start_date=MONDAY - timedelta(days=1),
        )
        log(active_user, meal, chicken, MONDAY, quantity="1000")

        response = auth_client.get("/api/v1/analysis/weekly/", {"from": MONDAY.isoformat()})

        assert response.data["adherence"] == {"days_measured": 1, "days_within_goal": 1}

    def test_la_variation_de_poids_est_renvoyee(self, auth_client, active_user):
        WeightEntry.objects.create(user=active_user, date=MONDAY, weight_kg=Decimal("80"))
        WeightEntry.objects.create(user=active_user, date=SUNDAY, weight_kg=Decimal("79"))

        response = auth_client.get("/api/v1/analysis/weekly/", {"from": MONDAY.isoformat()})

        assert Decimal(response.data["weight_change"]) == Decimal("-1.00")
        assert len(response.data["weight"]["points"]) == 2


class TestReportSummary:
    def test_les_journees_tenues_sont_listees(self, auth_client, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        response = auth_client.get("/api/v1/reports/summary/", PERIOD)

        assert response.status_code == 200
        assert [day["date"] for day in response.data["days"]] == [MONDAY.isoformat()]

    def test_une_periode_vide_ne_renvoie_pas_des_zeros(self, auth_client):
        response = auth_client.get("/api/v1/reports/summary/", PERIOD)

        assert response.data["days"] == []
        assert response.data["averages"]["energy_kcal"] is None


class TestExports:
    def test_le_csv_est_un_fichier_attache(self, auth_client, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        response = auth_client.post("/api/v1/reports/csv/", PERIOD, format="json")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        assert "attachment" in response["Content-Disposition"]
        assert "20260831-20260906" in response["Content-Disposition"]

    def test_le_csv_porte_une_ligne_par_journee_tenue(
        self, auth_client, active_user, meal, chicken
    ):
        log(active_user, meal, chicken, MONDAY)

        response = auth_client.post("/api/v1/reports/csv/", PERIOD, format="json")
        texte = response.content.decode("utf-8-sig")
        lignes = list(csv.reader(io.StringIO(texte)))

        assert lignes[0][0] == "date"
        assert lignes[1][0] == MONDAY.isoformat()

    def test_le_pdf_est_un_fichier_attache(self, auth_client, active_user, meal, chicken):
        log(active_user, meal, chicken, MONDAY)

        response = auth_client.post("/api/v1/reports/pdf/", PERIOD, format="json")

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

    def test_une_periode_invalide_est_refusee(self, auth_client):
        response = auth_client.post(
            "/api/v1/reports/csv/",
            {"from": SUNDAY.isoformat(), "to": MONDAY.isoformat()},
            format="json",
        )

        assert response.status_code == 400


class TestPermissions:
    @pytest.fixture
    def other_user(self, db) -> User:
        return User.objects.create_user(
            username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
        )

    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/analysis/food/",
            "/api/v1/analysis/weekly/",
            "/api/v1/reports/summary/",
        ],
    )
    def test_un_anonyme_est_refuse(self, api_client, url):
        assert api_client.get(url).status_code == 401

    @pytest.mark.parametrize("url", ["/api/v1/reports/csv/", "/api/v1/reports/pdf/"])
    def test_un_anonyme_ne_peut_pas_exporter(self, api_client, url):
        assert api_client.post(url, {}, format="json").status_code == 401

    def test_les_donnees_d_un_autre_compte_ne_sont_jamais_agregees(
        self, auth_client, other_user, chicken
    ):
        autre_repas = meal_types_for(other_user).first()
        log(other_user, autre_repas, chicken, MONDAY, quantity="500")

        response = auth_client.get("/api/v1/analysis/food/", PERIOD)

        assert response.data["sources"] == []
        assert response.data["logged_days"] == 0

    def test_un_compte_suspendu_est_refuse(self, active_user, meal, chicken):
        """401 : le jeton d'un compte suspendu est refusé avant la permission."""
        log(active_user, meal, chicken, MONDAY)
        client = client_for(active_user)
        active_user.status = UserStatus.SUSPENDED
        active_user.save(update_fields=["status"])

        assert client.get("/api/v1/analysis/weekly/").status_code == 401
