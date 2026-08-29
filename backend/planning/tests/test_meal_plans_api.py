"""API du planning (spec 04 §8).

La génération **ne persiste rien** : elle propose. C'est `POST /meal-plans/`
qui écrit, une fois la proposition relue — même règle que les autres endpoints
IA (spec 07 §5).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings as django_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from accounts.services.sessions import build_refresh_token
from common.models import AppSetting, AsyncTask, TaskStatus, TaskType
from diary.models import DiaryEntry
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from nutrition.services.goals import create_goal
from planning.models import MealPlan, PlanEntryType
from planning.services import plans

pytestmark = pytest.mark.django_db

MONDAY = date(2026, 8, 31)
LIST_URL = reverse("api-v1:meal-plans:list")
GENERATE_URL = reverse("api-v1:meal-plans:generate")


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[django_settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[django_settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="p1", name="Poulet rôti", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"), protein_g=Decimal("25"))
    return food


@pytest.fixture
def apricot(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="a1", name="Abricot cru", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("48"))
    return food


@pytest.fixture
def ai_enabled(settings):
    """Configuration minimale pour que la génération réponde."""
    settings.AI_ENABLED = True
    settings.AI_PROVIDER = "fake"
    settings.AI_MEAL_SCAN_MODEL = "modele-de-test"
    settings.AI_MEAL_PLANNER_MODEL = "modele-de-test"
    return settings


@pytest.fixture
def meals(active_user):
    return {meal.system_key: meal for meal in meal_types_for(active_user)}


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


def plan_body(meals, chicken, *, days: int = 1) -> dict:
    return {
        "name": "Semaine test",
        "generated_by_ai": True,
        "days": [
            {
                "date": (MONDAY + timedelta(days=offset)).isoformat(),
                "entries": [
                    {
                        "meal_type_id": meals["lunch"].pk,
                        "entry_type": PlanEntryType.FOOD,
                        "food_id": chicken.pk,
                        "quantity": "150",
                        "unit_label": "g",
                    }
                ],
            }
            for offset in range(days)
        ],
    }


class TestGeneration:
    def test_la_generation_ne_persiste_rien(self, ai_enabled, active_user, goal, chicken, apricot):
        """Elle propose ; `POST /meal-plans/` écrira."""
        response = client_for(active_user).post(
            GENERATE_URL,
            {
                "start_date": MONDAY.isoformat(),
                "end_date": MONDAY.isoformat(),
                "meal_type_ids": [meal.pk for meal in meal_types_for(active_user)[:2]],
            },
            format="json",
        )

        assert response.status_code == 202
        assert MealPlan.objects.count() == 0

    def test_la_proposition_porte_les_totaux_recalcules(
        self, ai_enabled, active_user, goal, chicken, apricot
    ):
        response = client_for(active_user).post(
            GENERATE_URL,
            {
                "start_date": MONDAY.isoformat(),
                "end_date": MONDAY.isoformat(),
                "meal_type_ids": [meal_types_for(active_user)[0].pk],
            },
            format="json",
        )

        jour = response.json()["result"]["days"][0]
        element = jour["meals"][0]["items"][0]

        # Le fournisseur simulé propose 150 g ; le dosage les ajuste pour
        # approcher la cible, et les totaux suivent les fiches — 200 kcal aux
        # 100 g pour ce poulet, jamais un chiffre annoncé par le modèle.
        quantite = Decimal(element["quantity"])
        assert quantite > Decimal("150")
        assert Decimal(element["values"]["energy_kcal"]) == quantite * 2
        assert Decimal(jour["totals"]["energy_kcal"]) == quantite * 2
        assert "daily_calories" in jour["deviations"]

    def test_la_tache_porte_son_type(self, ai_enabled, active_user, goal, chicken, apricot):
        client_for(active_user).post(
            GENERATE_URL,
            {
                "start_date": MONDAY.isoformat(),
                "end_date": MONDAY.isoformat(),
                "meal_type_ids": [meal_types_for(active_user)[0].pk],
            },
            format="json",
        )

        assert AsyncTask.objects.get().task_type == TaskType.MEAL_PLANNER

    def test_sans_objectif_la_generation_echoue_proprement(self, ai_enabled, active_user, chicken):
        client_for(active_user).post(
            GENERATE_URL,
            {
                "start_date": MONDAY.isoformat(),
                "end_date": MONDAY.isoformat(),
                "meal_type_ids": [meal_types_for(active_user)[0].pk],
            },
            format="json",
        )

        task = AsyncTask.objects.get()
        assert task.status == TaskStatus.FAILED
        assert "objectif" in task.error

    def test_une_periode_trop_longue_est_refusee(self, ai_enabled, active_user, goal):
        """Chaque journée coûte un appel au modèle."""
        response = client_for(active_user).post(
            GENERATE_URL,
            {
                "start_date": MONDAY.isoformat(),
                "end_date": (MONDAY + timedelta(days=20)).isoformat(),
                "meal_type_ids": [meal_types_for(active_user)[0].pk],
            },
            format="json",
        )

        assert response.status_code == 400

    def test_l_ia_coupee_repond_503(self, ai_enabled, active_user, goal):
        AppSetting.objects.create(key=AppSetting.AI_ENABLED, value=False)

        response = client_for(active_user).post(
            GENERATE_URL,
            {
                "start_date": MONDAY.isoformat(),
                "end_date": MONDAY.isoformat(),
                "meal_type_ids": [meal_types_for(active_user)[0].pk],
            },
            format="json",
        )

        assert response.status_code == 503
        assert response.json()["code"] == "ai_disabled"


class TestPlans:
    def test_un_plan_s_enregistre(self, active_user, meals, chicken):
        response = client_for(active_user).post(
            LIST_URL, plan_body(meals, chicken, days=2), format="json"
        )

        assert response.status_code == 201
        assert response.json()["days_count"] == 2
        assert response.json()["skipped_recipes"] == []

    def test_la_liste_ne_montre_que_les_siens(self, active_user, other_user, meals, chicken):
        client_for(active_user).post(LIST_URL, plan_body(meals, chicken), format="json")

        assert client_for(other_user).get(LIST_URL).json()["count"] == 0

    def test_le_plan_d_un_autre_repond_404(self, active_user, other_user, meals, chicken):
        plan, _ = plans.create_plan(
            user=active_user,
            payload={
                "name": "Mien",
                "days": [{"date": MONDAY, "entries": []}],
            },
        )
        url = reverse("api-v1:meal-plans:detail", args=[plan.pk])

        assert client_for(other_user).get(url).status_code == 404

    def test_la_journee_porte_ses_totaux_et_son_ecart(self, active_user, meals, chicken, goal):
        created = (
            client_for(active_user).post(LIST_URL, plan_body(meals, chicken), format="json").json()
        )

        jour = created["days"][0]
        assert Decimal(jour["totals"]["energy_kcal"]) == Decimal("300")
        assert Decimal(jour["targets"]["daily_calories"]) == Decimal("2000")
        assert jour["deviations"]["daily_calories"] < 0

    def test_un_appel_anonyme_est_refuse(self, db):
        assert APIClient().get(LIST_URL).status_code == 401


class TestAddToDiary:
    def add_url(self, plan) -> str:
        return reverse("api-v1:meal-plans:add-to-diary", args=[plan.pk])

    def test_le_plan_se_verse_au_journal(self, active_user, meals, chicken):
        plan_id = (
            client_for(active_user)
            .post(LIST_URL, plan_body(meals, chicken), format="json")
            .json()["id"]
        )
        plan = MealPlan.objects.get(pk=plan_id)

        response = client_for(active_user).post(self.add_url(plan), {}, format="json")

        assert response.status_code == 201
        assert DiaryEntry.objects.count() == 1

    def test_un_repas_deja_rempli_arrete_l_ajout(self, active_user, meals, chicken):
        """Rien n'est écrit tant que l'utilisateur n'a pas confirmé (spec 01 §15)."""
        entries_service.create_food_entry(
            user=active_user,
            food=chicken,
            day=MONDAY,
            meal_type=meals["lunch"],
            quantity=Decimal("100"),
            unit_label="g",
            consumed_at=plans._moment_on(MONDAY),
        )
        plan_id = (
            client_for(active_user)
            .post(LIST_URL, plan_body(meals, chicken), format="json")
            .json()["id"]
        )
        plan = MealPlan.objects.get(pk=plan_id)

        response = client_for(active_user).post(self.add_url(plan), {}, format="json")

        assert response.json()["conflicts"] == ["31/08 — Déjeuner"]
        assert response.json()["entries"] == []
        assert DiaryEntry.objects.count() == 1

    def test_confirme_l_ajout_se_fait_par_dessus(self, active_user, meals, chicken):
        entries_service.create_food_entry(
            user=active_user,
            food=chicken,
            day=MONDAY,
            meal_type=meals["lunch"],
            quantity=Decimal("100"),
            unit_label="g",
            consumed_at=plans._moment_on(MONDAY),
        )
        plan_id = (
            client_for(active_user)
            .post(LIST_URL, plan_body(meals, chicken), format="json")
            .json()["id"]
        )
        plan = MealPlan.objects.get(pk=plan_id)

        response = client_for(active_user).post(
            self.add_url(plan), {"confirm": True}, format="json"
        )

        assert response.status_code == 201
        # L'existante survit : rien n'est remplacé.
        assert DiaryEntry.objects.count() == 2

    def test_le_plan_d_un_autre_ne_se_verse_pas(self, active_user, other_user, meals, chicken):
        plan_id = (
            client_for(active_user)
            .post(LIST_URL, plan_body(meals, chicken), format="json")
            .json()["id"]
        )
        plan = MealPlan.objects.get(pk=plan_id)

        assert client_for(other_user).post(self.add_url(plan), {}, format="json").status_code == 404


class TestShoppingFromPlan:
    def test_meal_plan_id_est_accepte(self, active_user, meals, chicken):
        plan_id = (
            client_for(active_user)
            .post(LIST_URL, plan_body(meals, chicken), format="json")
            .json()["id"]
        )

        response = client_for(active_user).post(
            reverse("api-v1:shopping-lists:generate"),
            {"meal_plan_id": plan_id, "name": "Courses du plan"},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["items"][0]["name"] == "Poulet rôti"

    def test_sans_aucune_source_la_generation_est_refusee(self, active_user):
        response = client_for(active_user).post(
            reverse("api-v1:shopping-lists:generate"), {"name": "Vide"}, format="json"
        )

        assert response.status_code == 400
