"""API des repas enregistrés (spec 01 §13, spec 04 §7)."""

from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from diary.models import DiaryEntry, EntryType
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from recipes.models import ItemType, Recipe, RecipeIngredient, SavedMeal, SavedMealItem
from recipes.services import nutrition as nutrition_service

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api-v1:saved-meals:list")
TODAY = date(2026, 8, 26)


def detail_url(saved_meal) -> str:
    return reverse("api-v1:saved-meals:detail", args=[saved_meal.pk])


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"))
    return food


@pytest.fixture
def recipe(active_user, chicken) -> Recipe:
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


@pytest.fixture
def saved_meal(active_user, chicken, recipe) -> SavedMeal:
    meal = SavedMeal.objects.create(owner=active_user, name="Mon déjeuner")
    SavedMealItem.objects.create(
        saved_meal=meal,
        item_type=ItemType.FOOD,
        food=chicken,
        item_name=chicken.name,
        quantity=Decimal("150"),
        unit_label="g",
    )
    SavedMealItem.objects.create(
        saved_meal=meal,
        item_type=ItemType.RECIPE,
        recipe=recipe,
        item_name=recipe.name,
        quantity=Decimal("1"),
        unit_label="portion",
        sort_order=1,
    )
    return meal


def add_to_diary(client, saved_meal, user):
    return client.post(
        reverse("api-v1:saved-meals:add-to-diary", args=[saved_meal.pk]),
        {"date": TODAY.isoformat(), "meal_type_id": meal_types_for(user).first().id},
        format="json",
    )


# --- Création ---------------------------------------------------------------


def test_creation_dun_repas_enregistre(auth_client, active_user, chicken, recipe):
    response = auth_client.post(
        LIST_URL,
        {
            "name": "Mon déjeuner",
            "items": [
                {"item_type": "food", "food_id": chicken.id, "quantity": "150", "unit_label": "g"},
                {"item_type": "recipe", "recipe_id": recipe.id, "quantity": "1"},
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    assert len(response.data["items"]) == 2
    assert SavedMeal.objects.get().owner == active_user


def test_un_element_sans_source_est_refuse(auth_client):
    response = auth_client.post(
        LIST_URL,
        {"name": "Vide", "items": [{"item_type": "food", "quantity": "1"}]},
        format="json",
    )

    assert response.status_code == 400


def test_une_recette_invisible_est_refusee(auth_client, other_user):
    foreign = Recipe.objects.create(owner=other_user, name="Privée", servings=Decimal("1"))

    response = auth_client.post(
        LIST_URL,
        {
            "name": "Vol",
            "items": [{"item_type": "recipe", "recipe_id": foreign.id, "quantity": "1"}],
        },
        format="json",
    )

    assert response.status_code == 400


# --- Ajout au journal -------------------------------------------------------


def test_lajout_deplie_en_entrees_independantes(auth_client, active_user, saved_meal):
    """Chaque élément devient une entrée normale et snapshotée (spec 01 §13)."""
    response = add_to_diary(auth_client, saved_meal, active_user)

    assert response.status_code == 201
    assert len(response.data["entries"]) == 2
    assert response.data["skipped"] == []

    types = set(DiaryEntry.objects.values_list("entry_type", flat=True))
    assert types == {EntryType.FOOD, EntryType.RECIPE}


def test_les_entrees_creees_ne_dependent_plus_du_repas(auth_client, active_user, saved_meal):
    add_to_diary(auth_client, saved_meal, active_user)
    saved_meal.items.all().delete()
    saved_meal.name = "Renommé"
    saved_meal.save()

    assert DiaryEntry.objects.count() == 2


def test_la_suppression_dun_element_ne_touche_pas_le_journal(auth_client, active_user, saved_meal):
    add_to_diary(auth_client, saved_meal, active_user)
    food_entry = DiaryEntry.objects.get(entry_type=EntryType.FOOD)

    saved_meal.delete()

    food_entry.refresh_from_db()
    assert entries_service.computed_nutrition(food_entry)["energy_kcal"] == Decimal("300")


def test_un_element_dont_la_source_a_disparu_est_signale(auth_client, active_user, saved_meal):
    """Ignoré plutôt qu'ignoré en silence, et sans bloquer les autres."""
    orphan = saved_meal.items.get(item_type=ItemType.FOOD)
    orphan.food = None
    orphan.save()

    response = add_to_diary(auth_client, saved_meal, active_user)

    assert len(response.data["entries"]) == 1
    assert response.data["skipped"] == ["Poulet"]


def test_un_repas_dun_autre_compte_est_refuse(active_user, other_user, saved_meal):
    response = add_to_diary(client_for(other_user), saved_meal, other_user)

    assert response.status_code == 404


# --- Duplication, suppression, permissions ----------------------------------


def test_duplication_independante(auth_client, saved_meal):
    response = auth_client.post(reverse("api-v1:saved-meals:duplicate", args=[saved_meal.pk]))

    assert response.status_code == 201
    copy = SavedMeal.objects.get(pk=response.data["id"])
    assert copy.name.endswith("(copie)")
    assert copy.items.count() == 2

    copy.items.all().delete()
    assert saved_meal.items.count() == 2


def test_la_suppression_est_douce(auth_client, saved_meal):
    assert auth_client.delete(detail_url(saved_meal)).status_code == 204

    saved_meal.refresh_from_db()
    assert saved_meal.deleted_at is not None
    assert auth_client.get(detail_url(saved_meal)).status_code == 404


def test_les_repas_exigent_une_authentification(api_client):
    assert api_client.get(LIST_URL).status_code == 401


def test_un_repas_prive_est_invisible_aux_autres(active_user, other_user, saved_meal):
    client = client_for(other_user)

    assert client.get(detail_url(saved_meal)).status_code == 404
    assert client.get(LIST_URL).data["results"] == []


def test_un_repas_recu_nest_pas_modifiable(active_user, other_user, saved_meal):
    saved_meal.visibility = "app_users"
    saved_meal.save()

    client = client_for(other_user)
    assert client.get(detail_url(saved_meal)).status_code == 200
    assert client.patch(detail_url(saved_meal), {"name": "Volé"}, format="json").status_code == 404
