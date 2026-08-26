"""API du journal (spec 04 §4, spec 05 §12).

Les tests de permissions sont explicites : une entrée d'un autre compte ne doit
être ni lisible, ni modifiable, ni supprimable, même en devinant son
identifiant.
"""

from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserStatus
from accounts.services.sessions import build_refresh_token
from diary.models import DiaryEntry, EntryType, MealType
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import (
    Food,
    FoodNutrition,
    FoodSource,
    FoodVisibility,
    UserFoodHistory,
)
from nutrition.services.goals import create_goal

pytestmark = pytest.mark.django_db

DIARY_URL = reverse("api-v1:diary:day")
ENTRIES_URL = reverse("api-v1:diary:entry-create")


@pytest.fixture
def chicken(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="1",
        name="Poulet rôti",
        reference_amount=100,
    )
    FoodNutrition.objects.create(
        food=food,
        energy_kcal=Decimal("192"),
        protein_g=Decimal("17.3"),
        carbohydrates_g=Decimal("0"),
        fat_g=Decimal("13.5"),
    )
    return food


@pytest.fixture
def meal(active_user) -> MealType:
    return meal_types_for(active_user).first()


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


def payload(food, meal, **overrides) -> dict:
    return {
        "date": "2026-08-25",
        "meal_type_id": meal.id,
        "food_id": food.id,
        "quantity": "150",
        "unit_label": "g",
        **overrides,
    }


# --- Journée -----------------------------------------------------------------


def test_une_journee_vide_liste_les_repas(auth_client):
    response = auth_client.get(DIARY_URL, {"date": "2026-08-25"})

    assert response.status_code == 200
    assert [meal["meal_type"]["name"] for meal in response.data["meals"]] == [
        "Petit-déjeuner",
        "Déjeuner",
        "Dîner",
        "Collations",
    ]
    assert response.data["totals"]["energy_kcal"] == "0.000"


def test_une_date_invalide_est_refusee(auth_client):
    response = auth_client.get(DIARY_URL, {"date": "pas-une-date"})

    assert response.status_code == 400
    assert response.data["code"] == "validation_error"


def test_la_journee_agrege_totaux_et_repas(auth_client, chicken, meal):
    auth_client.post(ENTRIES_URL, payload(chicken, meal))

    response = auth_client.get(DIARY_URL, {"date": "2026-08-25"})

    assert response.data["totals"]["energy_kcal"] == "288.000"
    section = next(item for item in response.data["meals"] if item["meal_type"]["id"] == meal.id)
    assert section["totals"]["energy_kcal"] == "288.000"
    assert len(section["entries"]) == 1


def test_la_journee_expose_les_objectifs_et_le_restant(auth_client, active_user, chicken, meal):
    create_goal(
        user=active_user,
        daily_calories=Decimal("2000"),
        protein_g=Decimal("150"),
        carbs_g=Decimal("200"),
        fat_g=Decimal("67"),
        start_date=timezone.localdate().replace(day=1),
    )
    auth_client.post(ENTRIES_URL, payload(chicken, meal))

    response = auth_client.get(DIARY_URL, {"date": "2026-08-25"})

    assert response.data["goals"] is not None
    assert Decimal(response.data["remaining"]["daily_calories"]) == Decimal("1712.000")


# --- Ajout -------------------------------------------------------------------


def test_un_aliment_peut_etre_journalise(auth_client, chicken, meal):
    response = auth_client.post(ENTRIES_URL, payload(chicken, meal))

    assert response.status_code == 201
    assert response.data["snapshot_name"] == "Poulet rôti"
    assert response.data["computed"]["energy_kcal"] == "288.000"


def test_l_ajout_alimente_les_recents(auth_client, active_user, chicken, meal):
    """Régression : sans cet effet, la page Aliments resterait vide."""
    auth_client.post(ENTRIES_URL, payload(chicken, meal))

    assert UserFoodHistory.objects.filter(user=active_user, food=chicken).exists()

    recent = auth_client.get(reverse("api-v1:foods:recent"))
    assert [item["name"] for item in recent.data["results"]] == ["Poulet rôti"]


def test_une_unite_incalculable_est_refusee(auth_client, chicken, meal):
    response = auth_client.post(ENTRIES_URL, payload(chicken, meal, unit_label="cuillère à soupe"))

    assert response.status_code == 400
    assert "unit_label" in response.data["errors"]


def test_une_quantite_nulle_est_refusee(auth_client, chicken, meal):
    response = auth_client.post(ENTRIES_URL, payload(chicken, meal, quantity="0"))

    assert response.status_code == 400


def test_l_horodatage_est_automatique(auth_client, chicken, meal):
    response = auth_client.post(ENTRIES_URL, payload(chicken, meal))

    assert response.data["consumed_at"] is not None


def test_un_ajout_rapide_ne_demande_que_des_calories(auth_client, meal):
    response = auth_client.post(
        ENTRIES_URL,
        {
            "date": "2026-08-25",
            "meal_type_id": meal.id,
            "entry_type": EntryType.QUICK_ADD,
            "energy_kcal": "250",
            "name": "Restaurant",
        },
    )

    assert response.status_code == 201
    assert response.data["computed"]["energy_kcal"] == "250.000"


def test_un_ajout_rapide_sans_calories_est_refuse(auth_client, meal):
    response = auth_client.post(
        ENTRIES_URL,
        {"date": "2026-08-25", "meal_type_id": meal.id, "entry_type": EntryType.QUICK_ADD},
    )

    assert response.status_code == 400
    assert "energy_kcal" in response.data["errors"]


# --- Modification et suppression ---------------------------------------------


def test_la_quantite_peut_etre_modifiee(auth_client, chicken, meal):
    created = auth_client.post(ENTRIES_URL, payload(chicken, meal)).data
    url = reverse("api-v1:diary:entry-detail", args=[created["id"]])

    response = auth_client.patch(url, {"quantity": "300"})

    assert response.status_code == 200
    assert response.data["computed"]["energy_kcal"] == "576.000"


def test_une_entree_peut_changer_de_repas(auth_client, active_user, chicken, meal):
    created = auth_client.post(ENTRIES_URL, payload(chicken, meal)).data
    dinner = meal_types_for(active_user).order_by("sort_order")[2]
    url = reverse("api-v1:diary:entry-detail", args=[created["id"]])

    response = auth_client.patch(url, {"meal_type_id": dinner.id})

    assert response.status_code == 200
    assert response.data["meal_type_id"] == dinner.id


def test_une_entree_peut_etre_supprimee(auth_client, chicken, meal):
    created = auth_client.post(ENTRIES_URL, payload(chicken, meal)).data
    url = reverse("api-v1:diary:entry-detail", args=[created["id"]])

    assert auth_client.delete(url).status_code == 204
    assert not DiaryEntry.objects.filter(pk=created["id"]).exists()


def test_changer_d_unite_sans_aliment_est_refuse(auth_client, chicken, meal):
    """Seule la quantité reste modifiable quand la source a disparu."""
    created = auth_client.post(ENTRIES_URL, payload(chicken, meal)).data
    chicken.delete()
    url = reverse("api-v1:diary:entry-detail", args=[created["id"]])

    response = auth_client.patch(url, {"unit_label": "kg"})

    assert response.status_code == 400
    assert "unit_label" in response.data["errors"]


# --- Permissions -------------------------------------------------------------


def test_un_visiteur_anonyme_est_refuse(api_client):
    assert api_client.get(DIARY_URL).status_code == 401


def test_un_compte_non_actif_est_refuse(db):
    user = User.objects.create_user(
        username="attente", password="un-mot-de-passe-solide-1", status=UserStatus.PENDING
    )

    assert client_for(user).get(DIARY_URL).status_code == 401


def test_une_entree_d_un_autre_compte_est_invisible(auth_client, other_user, chicken):
    foreign_meal = meal_types_for(other_user).first()
    entry = entries_service.create_food_entry(
        user=other_user,
        food=chicken,
        day=timezone.localdate(),
        meal_type=foreign_meal,
        quantity=Decimal("100"),
        unit_label="g",
        consumed_at=timezone.now(),
    )
    url = reverse("api-v1:diary:entry-detail", args=[entry.id])

    assert auth_client.patch(url, {"quantity": "500"}).status_code == 404
    assert auth_client.delete(url).status_code == 404
    entry.refresh_from_db()
    assert entry.quantity == Decimal("100.000")


def test_le_repas_d_un_autre_compte_ne_peut_pas_servir(auth_client, other_user, chicken):
    foreign_meal = meal_types_for(other_user).first()

    response = auth_client.post(ENTRIES_URL, payload(chicken, foreign_meal))

    assert response.status_code == 400
    assert "meal_type_id" in response.data["errors"]


def test_un_aliment_invisible_ne_peut_pas_etre_journalise(auth_client, other_user, meal):
    """Le filtrage passe par `visible_to`, écrit à l'étape 4."""
    private = Food.objects.create(
        source=FoodSource.USER,
        owner=other_user,
        name="Secret",
        visibility=FoodVisibility.PRIVATE,
        reference_amount=100,
    )
    FoodNutrition.objects.create(food=private, energy_kcal=Decimal("100"))

    response = auth_client.post(ENTRIES_URL, payload(private, meal))

    assert response.status_code == 400
    assert "food_id" in response.data["errors"]


def test_la_journee_d_un_autre_compte_n_est_pas_agregee(auth_client, other_user, chicken):
    foreign_meal = meal_types_for(other_user).first()
    entries_service.create_food_entry(
        user=other_user,
        food=chicken,
        day=timezone.localdate(),
        meal_type=foreign_meal,
        quantity=Decimal("100"),
        unit_label="g",
        consumed_at=timezone.now(),
    )

    response = auth_client.get(DIARY_URL)

    assert response.data["totals"]["energy_kcal"] == "0.000"


# --- Suppression de compte ---------------------------------------------------


def test_supprimer_un_compte_emporte_son_journal(auth_client, active_user, chicken, meal):
    """Régression : la suppression d'un compte doit emporter son journal.

    Une contrainte `PROTECT` sur le repas la faisait échouer avec une erreur de
    base de données dès qu'une entrée existait, alors que la suppression est
    définitive et doit aboutir (spec 05 §11).
    """
    auth_client.post(ENTRIES_URL, payload(chicken, meal))
    assert DiaryEntry.objects.filter(diary_day__user=active_user).exists()

    response = auth_client.delete(
        reverse("api-v1:account:account"), {"username_confirmation": active_user.username}
    )

    assert response.status_code == 204
    assert not User.objects.filter(pk=active_user.pk).exists()
    assert not DiaryEntry.objects.exists()
    assert not MealType.objects.filter(user_id=active_user.pk).exists()
