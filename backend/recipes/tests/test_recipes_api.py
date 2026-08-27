"""API des recettes (spec 04 §6, spec 05 §7 et §12)."""

from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from diary.models import DiaryEntry, EntryType
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource, FoodVisibility
from recipes.models import Recipe, RecipeIngredient, RecipeVisibility
from recipes.services import nutrition as nutrition_service

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api-v1:recipes:list")
TODAY = date(2026, 8, 26)


def detail_url(recipe) -> str:
    return reverse("api-v1:recipes:detail", args=[recipe.pk])


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


def payload(chicken, **overrides) -> dict:
    return {
        "name": "Poulet riz",
        "servings": "2",
        "ingredients": [{"food_id": chicken.id, "quantity": "200", "unit_label": "g"}],
        **overrides,
    }


# --- Création et lecture ----------------------------------------------------


def test_creation_dune_recette(auth_client, active_user, chicken):
    response = auth_client.post(LIST_URL, payload(chicken), format="json")

    assert response.status_code == 201
    assert response.data["nutrition"]["energy_kcal"] == "200.000"
    assert len(response.data["ingredients"]) == 1
    assert Recipe.objects.get().owner == active_user


def test_le_proprietaire_nest_jamais_accepte_du_client(
    auth_client, active_user, other_user, chicken
):
    auth_client.post(LIST_URL, {**payload(chicken), "owner": other_user.id}, format="json")

    assert Recipe.objects.get().owner == active_user


def test_lecture_dune_recette(auth_client, recipe):
    response = auth_client.get(detail_url(recipe))

    assert response.status_code == 200
    assert response.data["name"] == "Poulet rôti"
    assert response.data["is_editable"] is True


def test_la_lecture_rafraichit_un_cache_perime(auth_client, recipe, chicken):
    chicken.nutrition.energy_kcal = Decimal("400")
    chicken.nutrition.save()
    chicken.save()

    response = auth_client.get(detail_url(recipe))

    assert response.data["nutrition"]["energy_kcal"] == "400.000"


def test_la_liste_signale_les_nutriments_partiels(auth_client, active_user, chicken):
    """Un total partiel n'est jamais présenté comme exact (spec 01 §8)."""
    auth_client.post(LIST_URL, payload(chicken), format="json")

    response = auth_client.get(LIST_URL)

    assert response.status_code == 200
    assert response.data["results"][0]["nutrition"]["fiber_g"] is None


# --- Modification -----------------------------------------------------------


def test_modification_remplace_les_ingredients(auth_client, recipe, chicken):
    response = auth_client.patch(
        detail_url(recipe),
        {"ingredients": [{"food_id": chicken.id, "quantity": "400", "unit_label": "g"}]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["nutrition"]["energy_kcal"] == "400.000"
    assert recipe.ingredients.count() == 1


def test_changer_les_portions_recalcule_le_cache(auth_client, recipe):
    response = auth_client.patch(detail_url(recipe), {"servings": "4"}, format="json")

    assert response.data["nutrition"]["energy_kcal"] == "100.000"


def test_un_nombre_de_portions_nul_est_refuse(auth_client, recipe):
    assert (
        auth_client.patch(detail_url(recipe), {"servings": "0"}, format="json").status_code == 400
    )


def test_une_unite_non_calculable_est_refusee(auth_client, chicken):
    """Jamais d'approximation : la conversion est refusée (spec 01 §9)."""
    response = auth_client.post(
        LIST_URL,
        payload(
            chicken, ingredients=[{"food_id": chicken.id, "quantity": "1", "unit_label": "cl"}]
        ),
        format="json",
    )

    assert response.status_code == 400


def test_un_aliment_invisible_est_refuse(auth_client, other_user):
    hidden = Food.objects.create(
        source=FoodSource.USER,
        owner=other_user,
        name="Secret",
        reference_amount=100,
        visibility=FoodVisibility.PRIVATE,
    )
    FoodNutrition.objects.create(food=hidden, energy_kcal=Decimal("100"))

    response = auth_client.post(
        LIST_URL,
        {
            "name": "Vol",
            "servings": "1",
            "ingredients": [{"food_id": hidden.id, "quantity": "100", "unit_label": "g"}],
        },
        format="json",
    )

    assert response.status_code == 400


def test_le_partage_cible_est_accepte(auth_client, chicken):
    """La visibilité dit combien ; `SharePermission` dit qui (spec 01 §18)."""
    response = auth_client.post(
        LIST_URL,
        payload(chicken, visibility=RecipeVisibility.SPECIFIC_USERS),
        format="json",
    )

    assert response.status_code == 201
    assert Recipe.objects.get().visibility == RecipeVisibility.SPECIFIC_USERS


# --- Suppression, duplication, favori ---------------------------------------


def test_la_suppression_est_douce(auth_client, recipe):
    assert auth_client.delete(detail_url(recipe)).status_code == 204

    recipe.refresh_from_db()
    assert recipe.deleted_at is not None
    assert auth_client.get(detail_url(recipe)).status_code == 404


def test_duplication_independante(auth_client, active_user, recipe):
    response = auth_client.post(reverse("api-v1:recipes:duplicate", args=[recipe.pk]))

    assert response.status_code == 201
    copy = Recipe.objects.get(pk=response.data["id"])
    assert copy.name.endswith("(copie)")
    assert copy.ingredients.count() == 1

    # Modifier la copie ne touche pas l'original.
    copy.ingredients.update(quantity=Decimal("999"))
    assert recipe.ingredients.first().quantity == Decimal("200")


def test_une_recette_partagee_se_copie_chez_soi(active_user, other_user, chicken):
    shared = Recipe.objects.create(
        owner=other_user,
        name="Partagée",
        servings=Decimal("1"),
        visibility=RecipeVisibility.APP_USERS,
    )

    response = client_for(active_user).post(reverse("api-v1:recipes:duplicate", args=[shared.pk]))

    assert response.status_code == 201
    copy = Recipe.objects.get(pk=response.data["id"])
    assert copy.owner == active_user
    # La copie repart en privé : elle ne reste pas publique sans le dire.
    assert copy.visibility == RecipeVisibility.PRIVATE


def test_favori(auth_client, recipe):
    url = reverse("api-v1:recipes:favorite", args=[recipe.pk])

    assert auth_client.post(url).status_code == 204
    recipe.refresh_from_db()
    assert recipe.is_favorite is True

    assert auth_client.delete(url).status_code == 204
    recipe.refresh_from_db()
    assert recipe.is_favorite is False


# --- Ajout au journal -------------------------------------------------------


def test_ajout_au_journal(auth_client, active_user, recipe):
    meal = meal_types_for(active_user).first()

    response = auth_client.post(
        reverse("api-v1:recipes:add-to-diary", args=[recipe.pk]),
        {"date": TODAY.isoformat(), "meal_type_id": meal.id, "servings": "2"},
        format="json",
    )

    assert response.status_code == 201
    entry = DiaryEntry.objects.get()
    assert entry.entry_type == EntryType.RECIPE
    assert entry.quantity == Decimal("2.000")
    assert response.data["computed"]["energy_kcal"] == "400.000"


def test_un_repas_dun_autre_compte_est_refuse(active_user, other_user, recipe):
    foreign_meal = meal_types_for(other_user).first()

    response = client_for(active_user).post(
        reverse("api-v1:recipes:add-to-diary", args=[recipe.pk]),
        {"date": TODAY.isoformat(), "meal_type_id": foreign_meal.id, "servings": "1"},
        format="json",
    )

    assert response.status_code == 404


# --- Permissions ------------------------------------------------------------


def test_les_recettes_exigent_une_authentification(api_client):
    assert api_client.get(LIST_URL).status_code == 401


def test_une_recette_privee_est_invisible_aux_autres(active_user, other_user, chicken):
    private = Recipe.objects.create(owner=other_user, name="Privée", servings=Decimal("1"))

    client = client_for(active_user)
    assert client.get(detail_url(private)).status_code == 404
    assert client.get(LIST_URL).data["results"] == []


def test_une_recette_partagee_est_lisible_mais_pas_modifiable(active_user, other_user):
    shared = Recipe.objects.create(
        owner=other_user,
        name="Partagée",
        servings=Decimal("1"),
        visibility=RecipeVisibility.APP_USERS,
    )

    client = client_for(active_user)
    response = client.get(detail_url(shared))
    assert response.status_code == 200
    assert response.data["is_editable"] is False

    assert client.patch(detail_url(shared), {"name": "Volée"}, format="json").status_code == 404
    assert client.delete(detail_url(shared)).status_code == 404


def test_la_suppression_du_compte_emporte_les_recettes(active_user, recipe):
    active_user.delete()

    assert Recipe.objects.count() == 0
