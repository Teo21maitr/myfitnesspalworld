"""Recherche d'aliments (spec 01 §7)."""

from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import User, UserStatus
from nutrition.models import (
    Food,
    FoodNutrition,
    FoodSource,
    FoodVisibility,
    UserFoodFavorite,
    UserFoodHistory,
)
from nutrition.services.search import (
    MINIMUM_QUERY_LENGTH,
    favorite_foods,
    frequent_foods,
    recent_foods,
    record_food_usage,
    search_foods,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def make_food(name: str, **overrides) -> Food:
    food = Food.objects.create(
        name=name, source=overrides.pop("source", FoodSource.CIQUAL), **overrides
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("100"))
    return food


def names(queryset) -> list[str]:
    return [food.name for food in queryset]


# --- Seuil de déclenchement ---------------------------------------------------


@pytest.mark.parametrize("query", ["", " ", "p"])
def test_une_requete_trop_courte_ne_renvoie_rien(active_user, query):
    make_food("Poulet")

    assert list(search_foods(active_user, query)) == []


def test_deux_caracteres_suffisent(active_user):
    make_food("Riz")

    assert MINIMUM_QUERY_LENGTH == 2
    assert names(search_foods(active_user, "ri")) == ["Riz"]


# --- Insensibilité et tolérance -----------------------------------------------


def test_la_recherche_ignore_la_casse(active_user):
    make_food("Poulet")

    assert names(search_foods(active_user, "POULET")) == ["Poulet"]


def test_la_recherche_ignore_les_accents(active_user):
    make_food("Pâtes")

    assert names(search_foods(active_user, "pates")) == ["Pâtes"]


def test_la_recherche_trouve_malgre_les_accents_saisis(active_user):
    make_food("Pates fraiches")

    assert names(search_foods(active_user, "pâtes")) == ["Pates fraiches"]


def test_la_recherche_tolere_une_faute_de_frappe(active_user):
    make_food("Chocolat noir")

    assert "Chocolat noir" in names(search_foods(active_user, "chocolats"))


def test_la_recherche_porte_aussi_sur_la_marque(active_user):
    make_food("Yaourt nature", brand="Danone")

    assert names(search_foods(active_user, "danone")) == ["Yaourt nature"]


def test_une_requete_sans_correspondance_ne_renvoie_rien(active_user):
    make_food("Poulet")

    assert list(search_foods(active_user, "zzzzzz")) == []


# --- Classement ---------------------------------------------------------------


def test_un_favori_passe_devant(active_user):
    make_food("Poulet rôti")
    favori = make_food("Poulet pané")
    UserFoodFavorite.objects.create(user=active_user, food=favori)

    assert names(search_foods(active_user, "poulet"))[0] == "Poulet pané"


def test_un_aliment_recent_passe_devant_un_inconnu(active_user):
    make_food("Poulet rôti")
    recent = make_food("Poulet pané")
    record_food_usage(active_user, recent)

    assert names(search_foods(active_user, "poulet"))[0] == "Poulet pané"


def test_le_favori_prime_sur_le_recent(active_user):
    recent = make_food("Poulet pané")
    favori = make_food("Poulet rôti")
    record_food_usage(active_user, recent)
    UserFoodFavorite.objects.create(user=active_user, food=favori)

    assert names(search_foods(active_user, "poulet"))[0] == "Poulet rôti"


def test_une_correspondance_exacte_passe_devant(active_user):
    make_food("Riz complet")
    make_food("Riz")

    assert names(search_foods(active_user, "riz"))[0] == "Riz"


def test_la_source_departage_a_egalite(active_user, other_user):
    """Les fiches officielles passent devant celles d'un autre utilisateur."""
    make_food(
        "Quinoa",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.APP_USERS,
    )
    make_food("Quinoa", source=FoodSource.CIQUAL)

    resultats = list(search_foods(active_user, "quinoa"))
    assert resultats[0].source == FoodSource.CIQUAL


# --- Visibilité ---------------------------------------------------------------


def test_la_recherche_ignore_les_aliments_prives_dautrui(active_user, other_user):
    make_food(
        "Poulet secret",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.PRIVATE,
    )

    assert list(search_foods(active_user, "poulet")) == []


def test_la_recherche_trouve_ses_propres_aliments_prives(active_user):
    make_food(
        "Poulet maison",
        source=FoodSource.USER,
        owner=active_user,
        visibility=FoodVisibility.PRIVATE,
    )

    assert names(search_foods(active_user, "poulet")) == ["Poulet maison"]


def test_la_recherche_ignore_les_aliments_desactives(active_user):
    make_food("Poulet", is_active=False)

    assert list(search_foods(active_user, "poulet")) == []


def test_la_recherche_ignore_les_aliments_supprimes(active_user):
    make_food("Poulet", deleted_at=timezone.now())

    assert list(search_foods(active_user, "poulet")) == []


# --- Récents, fréquents, favoris ----------------------------------------------


def test_les_recents_sont_antichronologiques(active_user):
    premier = make_food("Riz")
    second = make_food("Poulet")
    record_food_usage(active_user, premier)
    record_food_usage(active_user, second)

    assert names(recent_foods(active_user))[0] == "Poulet"


def test_les_recents_sont_limites(active_user):
    for index in range(5):
        record_food_usage(active_user, make_food(f"Aliment {index}"))

    assert len(list(recent_foods(active_user, limit=3))) == 3


def test_les_frequents_suivent_le_nombre_dutilisations(active_user):
    rare = make_food("Riz")
    courant = make_food("Poulet")
    record_food_usage(active_user, rare)
    for _ in range(3):
        record_food_usage(active_user, courant)

    assert names(frequent_foods(active_user))[0] == "Poulet"


def test_l_usage_incremente_le_compteur(active_user):
    food = make_food("Riz")

    record_food_usage(active_user, food)
    history = record_food_usage(active_user, food)

    assert history.use_count == 2
    assert UserFoodHistory.objects.filter(user=active_user, food=food).count() == 1


def test_les_favoris_sont_listes(active_user):
    food = make_food("Poulet")
    UserFoodFavorite.objects.create(user=active_user, food=food)

    assert names(favorite_foods(active_user)) == ["Poulet"]


def test_les_listes_personnelles_sont_isolees(active_user, other_user):
    food = make_food("Poulet")
    record_food_usage(other_user, food)
    UserFoodFavorite.objects.create(user=other_user, food=food)

    assert list(recent_foods(active_user)) == []
    assert list(favorite_foods(active_user)) == []
