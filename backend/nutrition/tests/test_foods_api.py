"""API du référentiel d'aliments (spec 04 §3, spec 05 §6)."""

from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from nutrition.models import (
    Food,
    FoodNutrition,
    FoodPortion,
    FoodSource,
    FoodVisibility,
    UserFoodFavorite,
)
from nutrition.services.search import record_food_usage

pytestmark = pytest.mark.django_db

SEARCH_URL = reverse("api-v1:foods:search")
LIST_URL = reverse("api-v1:foods:list")
RECENT_URL = reverse("api-v1:foods:recent")
FREQUENT_URL = reverse("api-v1:foods:frequent")
FAVORITES_URL = reverse("api-v1:foods:favorites")

NEW_FOOD = {
    "name": "Granola maison",
    "brand": "",
    "reference_amount": "100.00",
    "reference_unit": "g",
    "nutrition": {"energy_kcal": "450", "protein_g": "10", "carbohydrates_g": "60", "fat_g": "18"},
}


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    refresh = build_refresh_token(user)
    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(refresh.access_token)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = str(refresh)
    return client


def make_food(name: str, **overrides) -> Food:
    nutrition = overrides.pop("nutrition", {"energy_kcal": Decimal("120")})
    food = Food.objects.create(
        name=name, source=overrides.pop("source", FoodSource.CIQUAL), **overrides
    )
    FoodNutrition.objects.create(food=food, **nutrition)
    return food


# --- Recherche ----------------------------------------------------------------


def test_la_recherche_exige_une_authentification(api_client):
    assert api_client.get(SEARCH_URL, {"q": "poulet"}).status_code == 401


def test_la_recherche_renvoie_une_liste_paginee(auth_client):
    make_food("Poulet rôti")

    body = auth_client.get(SEARCH_URL, {"q": "poulet"}).json()

    assert body["count"] == 1
    assert body["results"][0]["name"] == "Poulet rôti"
    assert body["results"][0]["source_label"] == "Ciqual"


def test_la_recherche_expose_lenergie_et_le_favori(auth_client, active_user):
    food = make_food("Poulet")
    UserFoodFavorite.objects.create(user=active_user, food=food)

    result = auth_client.get(SEARCH_URL, {"q": "poulet"}).json()["results"][0]

    assert result["energy_kcal"] == "120.000"
    assert result["is_favorite"] is True


def test_une_requete_trop_courte_ne_renvoie_rien(auth_client):
    make_food("Poulet")

    assert auth_client.get(SEARCH_URL, {"q": "p"}).json()["count"] == 0


def test_la_recherche_sans_parametre_ne_renvoie_rien(auth_client):
    make_food("Poulet")

    assert auth_client.get(SEARCH_URL).json()["count"] == 0


# --- Fiche --------------------------------------------------------------------


def test_consultation_dune_fiche(auth_client):
    food = make_food(
        "Abricot",
        nutrition={"energy_kcal": Decimal("45.9"), "carbohydrates_g": Decimal("9.01")},
    )

    body = auth_client.get(reverse("api-v1:foods:detail", args=[food.pk])).json()

    assert body["name"] == "Abricot"
    assert body["nutrition"]["energy_kcal"] == "45.900"
    # Valeur non renseignée : nulle, jamais zéro (spec 01 §8).
    assert body["nutrition"]["vitamin_c_mg"] is None
    assert body["is_editable"] is False


def test_les_glucides_nets_sont_exposes(auth_client):
    food = make_food(
        "Pain",
        nutrition={"carbohydrates_g": Decimal("50"), "fiber_g": Decimal("6")},
    )

    body = auth_client.get(reverse("api-v1:foods:detail", args=[food.pk])).json()

    assert body["nutrition"]["net_carbs_g"] == "44.000"


def test_une_fiche_invisible_renvoie_404(active_user, other_user):
    food = make_food(
        "Secret",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.PRIVATE,
    )

    url = reverse("api-v1:foods:detail", args=[food.pk])
    assert client_for(active_user).get(url).status_code == 404


# --- Aliments personnels ------------------------------------------------------


def test_creation_dun_aliment_personnel(auth_client, active_user):
    response = auth_client.post(LIST_URL, NEW_FOOD, format="json")

    assert response.status_code == 201
    food = Food.objects.get(name="Granola maison")
    assert food.source == FoodSource.USER
    assert food.owner == active_user
    assert food.visibility == FoodVisibility.PRIVATE
    assert food.nutrition.energy_kcal == Decimal("450.000")


def test_lenergie_est_obligatoire(auth_client):
    payload = {**NEW_FOOD, "nutrition": {"protein_g": "10"}}

    response = auth_client.post(LIST_URL, payload, format="json")

    assert response.status_code == 400
    assert "nutrition" in response.json()["errors"]


def test_la_source_ne_peut_pas_etre_imposee(auth_client):
    """Le client ne décide jamais de la source ni du propriétaire."""
    response = auth_client.post(LIST_URL, {**NEW_FOOD, "source": FoodSource.CIQUAL}, format="json")

    assert response.status_code == 201
    assert Food.objects.get(name="Granola maison").source == FoodSource.USER


def test_le_partage_cible_est_accepte(auth_client):
    """La visibilité dit combien ; `SharePermission` dit qui (spec 01 §18)."""
    response = auth_client.post(
        LIST_URL, {**NEW_FOOD, "visibility": FoodVisibility.SPECIFIC_USERS}, format="json"
    )

    assert response.status_code == 201
    assert Food.objects.get(name="Granola maison").visibility == FoodVisibility.SPECIFIC_USERS


def test_modification_de_son_aliment(auth_client, active_user):
    food = make_food("Mon plat", source=FoodSource.USER, owner=active_user)

    response = auth_client.patch(
        reverse("api-v1:foods:detail", args=[food.pk]),
        {"name": "Mon plat revisité"},
        format="json",
    )

    assert response.status_code == 200
    food.refresh_from_db()
    assert food.name == "Mon plat revisité"
    assert food.search_text == "mon plat revisite"


def test_une_fiche_ciqual_nest_pas_modifiable(auth_client):
    """L'utilisateur crée sa propre version, il ne corrige pas la source."""
    food = make_food("Poulet")

    response = auth_client.patch(
        reverse("api-v1:foods:detail", args=[food.pk]), {"name": "Piraté"}, format="json"
    )

    assert response.status_code == 403
    food.refresh_from_db()
    assert food.name == "Poulet"


def test_laliment_dun_autre_nest_pas_modifiable(active_user, other_user):
    food = make_food(
        "Partagé",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.APP_USERS,
    )

    response = client_for(active_user).patch(
        reverse("api-v1:foods:detail", args=[food.pk]), {"name": "Volé"}, format="json"
    )

    assert response.status_code == 403
    food.refresh_from_db()
    assert food.name == "Partagé"


def test_suppression_douce_de_son_aliment(auth_client, active_user):
    food = make_food("Mon plat", source=FoodSource.USER, owner=active_user)

    response = auth_client.delete(reverse("api-v1:foods:detail", args=[food.pk]))

    assert response.status_code == 204
    food.refresh_from_db()
    # Suppression douce : la fiche existe encore pour l'historique du journal.
    assert food.is_active is False
    assert food.deleted_at is not None


def test_la_liste_ne_montre_que_ses_aliments(active_user, other_user):
    make_food("Ciqual")
    make_food("À moi", source=FoodSource.USER, owner=active_user)
    make_food("À l’autre", source=FoodSource.USER, owner=other_user)

    body = client_for(active_user).get(LIST_URL).json()

    assert body["count"] == 1
    assert body["results"][0]["name"] == "À moi"


# --- Favoris ------------------------------------------------------------------


def test_ajout_et_retrait_dun_favori(auth_client, active_user):
    food = make_food("Poulet")
    url = reverse("api-v1:foods:favorite", args=[food.pk])

    assert auth_client.post(url).status_code == 204
    assert UserFoodFavorite.objects.filter(user=active_user, food=food).exists()

    assert auth_client.delete(url).status_code == 204
    assert not UserFoodFavorite.objects.filter(user=active_user, food=food).exists()


def test_un_favori_pose_deux_fois_reste_unique(auth_client, active_user):
    food = make_food("Poulet")
    url = reverse("api-v1:foods:favorite", args=[food.pk])

    auth_client.post(url)
    auth_client.post(url)

    assert UserFoodFavorite.objects.filter(user=active_user).count() == 1


def test_impossible_de_mettre_en_favori_un_aliment_invisible(active_user, other_user):
    food = make_food(
        "Secret",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.PRIVATE,
    )

    url = reverse("api-v1:foods:favorite", args=[food.pk])
    assert client_for(active_user).post(url).status_code == 404


def test_liste_des_favoris(auth_client, active_user):
    food = make_food("Poulet")
    UserFoodFavorite.objects.create(user=active_user, food=food)

    assert auth_client.get(FAVORITES_URL).json()["results"][0]["name"] == "Poulet"


# --- Récents et fréquents -----------------------------------------------------


def test_recents_et_frequents(auth_client, active_user):
    food = make_food("Poulet")
    record_food_usage(active_user, food)

    assert auth_client.get(RECENT_URL).json()["count"] == 1
    assert auth_client.get(FREQUENT_URL).json()["count"] == 1


def test_recents_vides_au_depart(auth_client):
    make_food("Poulet")

    assert auth_client.get(RECENT_URL).json()["count"] == 0


# --- Portions -----------------------------------------------------------------


def test_ajout_dune_portion(auth_client, active_user):
    food = make_food("Pain de mie")

    response = auth_client.post(
        reverse("api-v1:foods:portions", args=[food.pk]),
        {"name": "1 tranche", "gram_equivalent": "32"},
        format="json",
    )

    assert response.status_code == 201
    portion = FoodPortion.objects.get(food=food)
    # Une portion posée sur un aliment global reste privée (spec 01 §9).
    assert portion.owner == active_user


def test_une_portion_sans_equivalence_est_refusee(auth_client):
    food = make_food("Pain de mie")

    response = auth_client.post(
        reverse("api-v1:foods:portions", args=[food.pk]),
        {"name": "1 tranche"},
        format="json",
    )

    assert response.status_code == 400


def test_les_portions_dautrui_restent_invisibles(active_user, other_user):
    food = make_food("Pain de mie")
    FoodPortion.objects.create(
        food=food, owner=other_user, name="1 grosse tranche", gram_equivalent=Decimal("50")
    )

    body = client_for(active_user).get(reverse("api-v1:foods:detail", args=[food.pk])).json()

    assert body["portions"] == []


def test_les_portions_officielles_sont_visibles_de_tous(active_user):
    food = make_food("Pain de mie")
    FoodPortion.objects.create(food=food, name="1 tranche", gram_equivalent=Decimal("32"))

    body = client_for(active_user).get(reverse("api-v1:foods:detail", args=[food.pk])).json()

    assert len(body["portions"]) == 1
    assert body["portions"][0]["is_own"] is False


def test_impossible_de_modifier_la_portion_dun_autre(active_user, other_user):
    food = make_food("Pain de mie")
    portion = FoodPortion.objects.create(
        food=food, owner=other_user, name="1 tranche", gram_equivalent=Decimal("32")
    )

    response = client_for(active_user).patch(
        reverse("api-v1:foods:portion-detail", args=[food.pk, portion.pk]),
        {"gram_equivalent": "99"},
        format="json",
    )

    assert response.status_code == 404
    portion.refresh_from_db()
    assert portion.gram_equivalent == Decimal("32.000")


def test_suppression_de_sa_portion(auth_client, active_user):
    food = make_food("Pain de mie")
    portion = FoodPortion.objects.create(
        food=food, owner=active_user, name="1 tranche", gram_equivalent=Decimal("32")
    )

    response = auth_client.delete(
        reverse("api-v1:foods:portion-detail", args=[food.pk, portion.pk])
    )

    assert response.status_code == 204
    assert FoodPortion.objects.count() == 0


# --- Compte non actif ---------------------------------------------------------


def test_un_compte_suspendu_na_pas_acces_aux_aliments(active_user):
    client = client_for(active_user)
    active_user.status = UserStatus.SUSPENDED
    active_user.save()

    assert client.get(SEARCH_URL, {"q": "poulet"}).status_code == 401
