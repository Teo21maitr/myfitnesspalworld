"""Types de repas (spec 01 §5, spec 04 §5)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserStatus
from diary.models import MealSystemKey, MealType
from diary.services import entries as entries_service
from diary.services.meal_types import ensure_meal_types, meal_types_for, remove
from nutrition.models import Food, FoodNutrition, FoodSource

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api-v1:meal-types:list")
REORDER_URL = reverse("api-v1:meal-types:reorder")


# --- Création par défaut -----------------------------------------------------


def test_les_quatre_repas_sont_crees_a_la_premiere_visite(active_user):
    ensure_meal_types(active_user)

    names = list(MealType.objects.filter(user=active_user).values_list("name", flat=True))

    assert names == ["Petit-déjeuner", "Déjeuner", "Dîner", "Collations"]


def test_la_creation_est_idempotente(active_user):
    ensure_meal_types(active_user)
    ensure_meal_types(active_user)

    assert MealType.objects.filter(user=active_user).count() == 4


def test_un_repas_desactive_n_est_pas_recree(active_user):
    """Réactiver ce que l'utilisateur a désactivé serait une régression."""
    ensure_meal_types(active_user)
    MealType.objects.filter(user=active_user, system_key=MealSystemKey.SNACKS).update(
        is_active=False
    )

    ensure_meal_types(active_user)

    assert not MealType.objects.get(user=active_user, system_key=MealSystemKey.SNACKS).is_active


def test_les_repas_sont_propres_a_chaque_compte(active_user, db):
    other = User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )
    ensure_meal_types(active_user)
    ensure_meal_types(other)

    MealType.objects.filter(user=active_user, system_key=MealSystemKey.LUNCH).update(name="Midi")

    assert MealType.objects.get(user=other, system_key=MealSystemKey.LUNCH).name == "Déjeuner"


# --- Suppression -------------------------------------------------------------


def test_supprimer_un_repas_systeme_le_desactive(active_user):
    ensure_meal_types(active_user)
    meal = MealType.objects.get(user=active_user, system_key=MealSystemKey.SNACKS)

    remove(meal)
    meal.refresh_from_db()

    assert meal.is_active is False
    assert MealType.objects.filter(pk=meal.pk).exists()


def test_supprimer_un_repas_personnel_le_supprime(active_user):
    meal = MealType.objects.create(user=active_user, name="Encas", slug="encas")

    remove(meal)

    assert not MealType.objects.filter(pk=meal.pk).exists()


def test_un_repas_deja_utilise_est_desactive_et_non_supprime(active_user):
    """L'historique prime : la clé étrangère est en PROTECT."""
    meal = MealType.objects.create(user=active_user, name="Encas", slug="encas")
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("192"))
    entries_service.create_food_entry(
        user=active_user,
        food=food,
        day=timezone.localdate(),
        meal_type=meal,
        quantity=Decimal("100"),
        unit_label="g",
        consumed_at=timezone.now(),
    )

    remove(meal)
    meal.refresh_from_db()

    assert meal.is_active is False


# --- API ---------------------------------------------------------------------


def test_la_liste_cree_les_repas_par_defaut(auth_client):
    response = auth_client.get(LIST_URL)

    assert response.status_code == 200
    assert [meal["name"] for meal in response.data] == [
        "Petit-déjeuner",
        "Déjeuner",
        "Dîner",
        "Collations",
    ]


def test_un_repas_peut_etre_renomme(auth_client, active_user):
    ensure_meal_types(active_user)
    meal = MealType.objects.get(user=active_user, system_key=MealSystemKey.LUNCH)
    url = reverse("api-v1:meal-types:detail", args=[meal.id])

    response = auth_client.patch(url, {"name": "Midi"})

    assert response.status_code == 200
    meal.refresh_from_db()
    assert meal.name == "Midi"
    # La clé système survit au renommage.
    assert meal.system_key == MealSystemKey.LUNCH


def test_un_repas_peut_etre_cree(auth_client, active_user):
    response = auth_client.post(LIST_URL, {"name": "Collation du soir"})

    assert response.status_code == 201
    assert response.data["is_system"] is False
    assert MealType.objects.filter(user=active_user, name="Collation du soir").exists()


def test_les_repas_peuvent_etre_reordonnes(auth_client, active_user):
    meals = list(meal_types_for(active_user).order_by("sort_order"))
    inverted = [meal.id for meal in reversed(meals)]

    response = auth_client.post(REORDER_URL, {"ids": inverted})

    assert response.status_code == 200
    assert [meal["id"] for meal in response.data] == inverted


def test_la_suppression_d_un_repas_systeme_repond_204_sans_le_supprimer(auth_client, active_user):
    ensure_meal_types(active_user)
    meal = MealType.objects.get(user=active_user, system_key=MealSystemKey.SNACKS)
    url = reverse("api-v1:meal-types:detail", args=[meal.id])

    response = auth_client.delete(url)

    assert response.status_code == 204
    assert MealType.objects.filter(pk=meal.pk, is_active=False).exists()


def test_un_utilisateur_ne_voit_pas_les_repas_d_un_autre(auth_client, db):
    other = User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )
    ensure_meal_types(other)
    foreign = MealType.objects.filter(user=other).first()
    url = reverse("api-v1:meal-types:detail", args=[foreign.id])

    assert auth_client.get(url).status_code == 404
    assert auth_client.patch(url, {"name": "Piraté"}).status_code == 404
