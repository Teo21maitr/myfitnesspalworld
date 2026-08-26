"""Tableau de bord et endpoints de copie (spec 04 §4 et §16)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserStatus
from diary.models import DiaryEntry, MealType
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource, FoodVisibility
from nutrition.services.goals import create_goal
from progress.models import WeightEntry

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()
TOMORROW = TODAY + timedelta(days=1)

DASHBOARD_URL = reverse("api-v1:dashboard:dashboard")
DIARY_URL = reverse("api-v1:diary:day")
COPY_DAY_URL = reverse("api-v1:diary:copy-day")
COPY_MEAL_URL = reverse("api-v1:diary:copy-meal")
BULK_ADD_URL = reverse("api-v1:diary:bulk-add")


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet rôti", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("192"))
    return food


@pytest.fixture
def meal(active_user) -> MealType:
    return meal_types_for(active_user).first()


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def add(user, food, meal, quantity="150", day=TODAY) -> DiaryEntry:
    return entries_service.create_food_entry(
        user=user,
        food=food,
        day=day,
        meal_type=meal,
        quantity=Decimal(quantity),
        unit_label="g",
        consumed_at=timezone.now(),
    )


# --- Tableau de bord -----------------------------------------------------------


def test_le_tableau_de_bord_d_un_compte_neuf_reste_lisible(auth_client):
    """Aucun objectif, aucune pesée : c'est le cas normal au démarrage."""
    response = auth_client.get(DASHBOARD_URL)

    assert response.status_code == 200
    assert response.data["goals"] is None
    assert response.data["remaining"] is None
    assert response.data["weight"]["latest_kg"] is None
    assert response.data["totals"]["energy_kcal"] == "0.000"


def test_le_tableau_de_bord_donne_le_meme_total_que_le_journal(
    auth_client, active_user, chicken, meal
):
    """Les deux écrans passent par le même service : ils ne doivent pas diverger."""
    add(active_user, chicken, meal)

    dashboard = auth_client.get(DASHBOARD_URL, {"date": TODAY.isoformat()})
    diary = auth_client.get(DIARY_URL, {"date": TODAY.isoformat()})

    assert dashboard.data["totals"] == diary.data["totals"]
    assert dashboard.data["meals"] == diary.data["meals"]


def test_le_tableau_de_bord_expose_le_poids_et_la_progression(auth_client, active_user):
    active_user.profile.target_weight_kg = Decimal("70")
    active_user.profile.save()
    WeightEntry.objects.create(user=active_user, date=TODAY - timedelta(days=30), weight_kg="80")
    WeightEntry.objects.create(user=active_user, date=TODAY, weight_kg="77.6")

    response = auth_client.get(DASHBOARD_URL)
    weight = response.data["weight"]

    assert Decimal(weight["latest_kg"]) == Decimal("77.60")
    assert Decimal(weight["change_kg"]) == Decimal("-2.40")
    assert Decimal(weight["target_kg"]) == Decimal("70.00")
    # 2,4 kg parcourus sur les 10 qui séparent 80 de 70.
    assert Decimal(weight["progress_percent"]) == Decimal("24.0")


def test_sans_poids_cible_la_progression_reste_inconnue(auth_client, active_user):
    WeightEntry.objects.create(user=active_user, date=TODAY, weight_kg="80")

    response = auth_client.get(DASHBOARD_URL)

    assert response.data["weight"]["progress_percent"] is None
    assert Decimal(response.data["weight"]["latest_kg"]) == Decimal("80.00")


def test_le_tableau_de_bord_reprend_les_objectifs_du_jour(auth_client, active_user, chicken, meal):
    create_goal(
        user=active_user,
        daily_calories=Decimal("2000"),
        protein_g=Decimal("150"),
        carbs_g=Decimal("200"),
        fat_g=Decimal("67"),
        start_date=TODAY.replace(day=1),
    )
    add(active_user, chicken, meal)

    response = auth_client.get(DASHBOARD_URL)

    assert Decimal(response.data["remaining"]["daily_calories"]) == Decimal("1712.000")


def test_le_tableau_de_bord_est_refuse_a_un_anonyme(api_client):
    assert api_client.get(DASHBOARD_URL).status_code == 401


# --- Duplication ---------------------------------------------------------------


def test_une_entree_peut_etre_dupliquee(auth_client, active_user, chicken, meal):
    entry = add(active_user, chicken, meal)
    url = reverse("api-v1:diary:entry-duplicate", args=[entry.id])

    response = auth_client.post(url, {})

    assert response.status_code == 201
    assert DiaryEntry.objects.count() == 2


def test_la_duplication_reprend_les_valeurs_actuelles(auth_client, active_user, chicken, meal):
    """La règle de la spec 01 §5, vérifiée jusqu'à l'API."""
    entry = add(active_user, chicken, meal)
    chicken.nutrition.energy_kcal = Decimal("500")
    chicken.nutrition.save()
    url = reverse("api-v1:diary:entry-duplicate", args=[entry.id])

    response = auth_client.post(url, {})

    assert response.data["computed"]["energy_kcal"] == "750.000"
    entry.refresh_from_db()
    assert entry.snapshot_energy_kcal == Decimal("192.000")


def test_une_entree_peut_etre_dupliquee_vers_une_autre_date(
    auth_client, active_user, chicken, meal
):
    entry = add(active_user, chicken, meal)
    url = reverse("api-v1:diary:entry-duplicate", args=[entry.id])

    auth_client.post(url, {"date": TOMORROW.isoformat()})

    assert DiaryEntry.objects.filter(diary_day__date=TOMORROW).count() == 1


# --- Copie ---------------------------------------------------------------------


def test_copier_une_journee_vers_plusieurs_dates(auth_client, active_user, chicken, meal):
    add(active_user, chicken, meal)
    after = TOMORROW + timedelta(days=1)

    response = auth_client.post(
        COPY_DAY_URL,
        {
            "source_date": TODAY.isoformat(),
            "target_dates": [TOMORROW.isoformat(), after.isoformat()],
        },
    )

    assert response.status_code == 201
    assert len(response.data) == 2
    assert DiaryEntry.objects.filter(diary_day__date=after).count() == 1


def test_copier_un_repas_vers_une_autre_date(auth_client, active_user, chicken, meal):
    add(active_user, chicken, meal)

    response = auth_client.post(
        COPY_MEAL_URL,
        {
            "source_date": TODAY.isoformat(),
            "source_meal_type_id": meal.id,
            "target_dates": [TOMORROW.isoformat()],
        },
    )

    assert response.status_code == 201
    assert DiaryEntry.objects.filter(diary_day__date=TOMORROW).count() == 1


def test_une_date_de_copie_invalide_est_refusee(auth_client):
    response = auth_client.post(
        COPY_DAY_URL, {"source_date": TODAY.isoformat(), "target_dates": ["pas-une-date"]}
    )

    assert response.status_code == 400


def test_une_copie_sans_date_cible_est_refusee(auth_client):
    response = auth_client.post(
        COPY_DAY_URL, {"source_date": TODAY.isoformat(), "target_dates": []}
    )

    assert response.status_code == 400


# --- Ajout sur plusieurs dates -------------------------------------------------


def test_un_aliment_peut_etre_ajoute_sur_plusieurs_dates(auth_client, chicken, meal):
    response = auth_client.post(
        BULK_ADD_URL,
        {
            "food_id": chicken.id,
            "meal_type_id": meal.id,
            "quantity": "100",
            "unit_label": "g",
            "target_dates": [TODAY.isoformat(), TOMORROW.isoformat()],
        },
    )

    assert response.status_code == 201
    assert DiaryEntry.objects.count() == 2


def test_une_unite_incalculable_est_refusee_en_ajout_multiple(auth_client, chicken, meal):
    response = auth_client.post(
        BULK_ADD_URL,
        {
            "food_id": chicken.id,
            "meal_type_id": meal.id,
            "quantity": "1",
            "unit_label": "cuillère à soupe",
            "target_dates": [TODAY.isoformat()],
        },
    )

    assert response.status_code == 400
    assert "unit_label" in response.data["errors"]


# --- Permissions ---------------------------------------------------------------


def test_dupliquer_l_entree_d_un_autre_est_refuse(auth_client, other_user, chicken):
    foreign_meal = meal_types_for(other_user).first()
    entry = add(other_user, chicken, foreign_meal)
    url = reverse("api-v1:diary:entry-duplicate", args=[entry.id])

    assert auth_client.post(url, {}).status_code == 404
    assert DiaryEntry.objects.count() == 1


def test_copier_le_repas_d_un_autre_est_refuse(auth_client, other_user, chicken):
    foreign_meal = meal_types_for(other_user).first()
    add(other_user, chicken, foreign_meal)

    response = auth_client.post(
        COPY_MEAL_URL,
        {
            "source_date": TODAY.isoformat(),
            "source_meal_type_id": foreign_meal.id,
            "target_dates": [TOMORROW.isoformat()],
        },
    )

    assert response.status_code == 400
    assert "source_meal_type_id" in response.data["errors"]


def test_copier_la_journee_d_un_autre_ne_copie_rien(auth_client, other_user, chicken):
    """Le service ne voit que les journées de l'appelant."""
    foreign_meal = meal_types_for(other_user).first()
    add(other_user, chicken, foreign_meal)

    response = auth_client.post(
        COPY_DAY_URL,
        {"source_date": TODAY.isoformat(), "target_dates": [TOMORROW.isoformat()]},
    )

    assert response.status_code == 201
    assert response.data == []


def test_un_aliment_invisible_ne_peut_pas_etre_ajoute_en_masse(auth_client, other_user, meal):
    private = Food.objects.create(
        source=FoodSource.USER,
        owner=other_user,
        name="Secret",
        visibility=FoodVisibility.PRIVATE,
    )
    FoodNutrition.objects.create(food=private, energy_kcal=Decimal("100"))

    response = auth_client.post(
        BULK_ADD_URL,
        {
            "food_id": private.id,
            "meal_type_id": meal.id,
            "quantity": "100",
            "unit_label": "g",
            "target_dates": [TODAY.isoformat()],
        },
    )

    assert response.status_code == 400
    assert "food_id" in response.data["errors"]
