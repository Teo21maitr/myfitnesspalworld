"""API de la liste de courses (spec 04 §11, spec 05 §7)."""

from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from nutrition.models import Food, FoodNutrition, FoodSource
from planning.models import ItemSource, ShoppingList, ShoppingListItem, ShoppingVisibility
from recipes.models import Recipe, RecipeIngredient
from social.models import ResourceType, SharePermission, VisibilityType

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api-v1:shopping-lists:list")
GENERATE_URL = reverse("api-v1:shopping-lists:generate")
TODAY = date(2026, 8, 26)


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"))
    return food


@pytest.fixture
def recipe(active_user, chicken) -> Recipe:
    recipe = Recipe.objects.create(owner=active_user, name="Plat", servings=Decimal("2"))
    RecipeIngredient.objects.create(
        recipe=recipe, food=chicken, food_name="Poulet", quantity=Decimal("150"), unit_label="g"
    )
    return recipe


@pytest.fixture
def basket(active_user) -> ShoppingList:
    return ShoppingList.objects.create(owner=active_user, name="Courses")


def detail_url(shopping_list) -> str:
    return reverse("api-v1:shopping-lists:detail", args=[shopping_list.pk])


def item_url(shopping_list, item) -> str:
    return reverse("api-v1:shopping-lists:item-detail", args=[shopping_list.pk, item.pk])


# --- Listes ------------------------------------------------------------------


def test_creation_dune_liste(auth_client, active_user):
    response = auth_client.post(LIST_URL, {"name": "Samedi"}, format="json")

    assert response.status_code == 201
    assert ShoppingList.objects.get().owner == active_user


def test_generation_depuis_une_recette(auth_client, recipe):
    response = auth_client.post(GENERATE_URL, {"recipe_ids": [recipe.id]}, format="json")

    assert response.status_code == 201
    assert [item["name"] for item in response.data["items"]] == ["Poulet"]
    assert response.data["items"][0]["quantity"] == "150.000"


def test_generer_dans_une_liste_existante_fusionne(auth_client, recipe, basket):
    auth_client.post(
        GENERATE_URL, {"shopping_list_id": basket.id, "recipe_ids": [recipe.id]}, format="json"
    )

    response = auth_client.post(
        GENERATE_URL, {"shopping_list_id": basket.id, "recipe_ids": [recipe.id]}, format="json"
    )

    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["quantity"] == "300.000"


def test_generer_sans_source_est_refuse(auth_client):
    assert auth_client.post(GENERATE_URL, {}, format="json").status_code == 400


def test_generer_dans_la_liste_dun_autre_est_refuse(active_user, other_user, recipe):
    foreign = ShoppingList.objects.create(owner=other_user, name="La sienne")

    response = client_for(active_user).post(
        GENERATE_URL,
        {"shopping_list_id": foreign.id, "recipe_ids": [recipe.id]},
        format="json",
    )

    assert response.status_code == 404


def test_la_suppression_dune_liste_est_franche(auth_client, basket):
    assert auth_client.delete(detail_url(basket)).status_code == 204
    assert not ShoppingList.objects.filter(pk=basket.pk).exists()


# --- Articles ----------------------------------------------------------------


def test_ajout_manuel(auth_client, basket):
    response = auth_client.post(
        reverse("api-v1:shopping-lists:items", args=[basket.pk]),
        {"name": "Sel", "quantity": "1", "unit_label": "paquet"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["source_type"] == ItemSource.MANUAL


def test_un_article_sans_quantite_est_accepte(auth_client, basket):
    """« Du sel » est un article valable (spec 01 §8)."""
    response = auth_client.post(
        reverse("api-v1:shopping-lists:items", args=[basket.pk]), {"name": "Sel"}, format="json"
    )

    assert response.status_code == 201
    assert response.data["quantity"] is None


def test_une_quantite_negative_est_refusee(auth_client, basket):
    response = auth_client.post(
        reverse("api-v1:shopping-lists:items", args=[basket.pk]),
        {"name": "Sel", "quantity": "-1"},
        format="json",
    )

    assert response.status_code == 400


def test_cocher_et_decocher_un_article(auth_client, basket):
    item = ShoppingListItem.objects.create(shopping_list=basket, name="Sel")

    assert auth_client.patch(item_url(basket, item), {"is_checked": True}, format="json").data[
        "is_checked"
    ]
    assert not auth_client.patch(item_url(basket, item), {"is_checked": False}, format="json").data[
        "is_checked"
    ]


def test_modifier_la_quantite(auth_client, basket, chicken):
    item = ShoppingListItem.objects.create(
        shopping_list=basket, name="Poulet", food=chicken, quantity=Decimal("150"), unit_label="g"
    )

    response = auth_client.patch(item_url(basket, item), {"quantity": "500"}, format="json")

    assert response.data["quantity"] == "500.000"


def test_supprimer_un_article(auth_client, basket):
    item = ShoppingListItem.objects.create(shopping_list=basket, name="Sel")

    assert auth_client.delete(item_url(basket, item)).status_code == 204
    assert basket.items.count() == 0


# --- Permissions et partage --------------------------------------------------


def test_les_courses_exigent_une_authentification(api_client):
    assert api_client.get(LIST_URL).status_code == 401


def test_la_liste_dun_autre_est_introuvable(active_user, other_user):
    foreign = ShoppingList.objects.create(owner=other_user, name="La sienne")

    client = client_for(active_user)
    assert client.get(detail_url(foreign)).status_code == 404
    assert client.patch(detail_url(foreign), {"name": "Volée"}, format="json").status_code == 404
    assert client.delete(detail_url(foreign)).status_code == 404


def test_une_liste_partagee_est_lisible(active_user, other_user):
    shared = ShoppingList.objects.create(
        owner=other_user, name="Partagée", visibility=ShoppingVisibility.APP_USERS
    )
    ShoppingListItem.objects.create(shopping_list=shared, name="Sel")

    response = client_for(active_user).get(detail_url(shared))

    assert response.status_code == 200
    assert response.data["is_editable"] is False


def test_une_liste_recue_ne_se_coche_pas(active_user, other_user):
    """Le partage donne à lire, jamais à écrire (spec 05 §7)."""
    shared = ShoppingList.objects.create(
        owner=other_user, name="Partagée", visibility=ShoppingVisibility.APP_USERS
    )
    item = ShoppingListItem.objects.create(shopping_list=shared, name="Sel")

    response = client_for(active_user).patch(
        item_url(shared, item), {"is_checked": True}, format="json"
    )

    assert response.status_code == 404
    item.refresh_from_db()
    assert item.is_checked is False


def test_un_partage_nomme_rend_la_liste_visible(active_user, other_user):
    shared = ShoppingList.objects.create(owner=other_user, name="Partagée")
    SharePermission.objects.create(
        owner=other_user,
        target_user=active_user,
        resource_type=ResourceType.SHOPPING_LIST,
        resource_id=shared.id,
        visibility_type=VisibilityType.SPECIFIC_USER,
    )

    assert client_for(active_user).get(detail_url(shared)).status_code == 200


def test_un_proprietaire_suspendu_ferme_sa_liste(active_user, other_user):
    shared = ShoppingList.objects.create(
        owner=other_user, name="Partagée", visibility=ShoppingVisibility.APP_USERS
    )
    other_user.status = UserStatus.SUSPENDED
    other_user.save()

    assert client_for(active_user).get(detail_url(shared)).status_code == 404


def test_repasser_une_liste_en_prive_revoque_ses_partages(auth_client, active_user, other_user):
    shopping_list = ShoppingList.objects.create(
        owner=active_user, name="Courses", visibility=ShoppingVisibility.APP_USERS
    )
    SharePermission.objects.create(
        owner=active_user,
        target_user=None,
        resource_type=ResourceType.SHOPPING_LIST,
        resource_id=shopping_list.id,
        visibility_type=VisibilityType.APP_USERS,
    )
    assert ShoppingList.objects.visible_to(other_user).filter(pk=shopping_list.pk).exists()

    auth_client.patch(
        detail_url(shopping_list), {"visibility": ShoppingVisibility.PRIVATE}, format="json"
    )

    assert not ShoppingList.objects.visible_to(other_user).filter(pk=shopping_list.pk).exists()
