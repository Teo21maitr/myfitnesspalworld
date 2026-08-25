"""Modèles et permissions du référentiel d'aliments (spec 01 §8 à §11, spec 05 §6)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from accounts.models import User, UserStatus
from nutrition.models import (
    Food,
    FoodNutrition,
    FoodPortion,
    FoodSource,
    FoodVisibility,
    normalize_search_text,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


def make_food(**overrides) -> Food:
    values = {
        "name": "Blanc de poulet",
        "source": FoodSource.CIQUAL,
        "external_id": None,
        **overrides,
    }
    return Food.objects.create(**values)


# --- Normalisation et recherche textuelle -------------------------------------


def test_normalisation_supprime_accents_et_casse():
    assert normalize_search_text("Pâtes CRUES") == "pates crues"


def test_normalisation_concatene_nom_et_marque():
    assert normalize_search_text("Yaourt", "Danône") == "yaourt danone"


def test_normalisation_ignore_les_parties_vides():
    assert normalize_search_text("Riz", None, "") == "riz"


def test_le_texte_de_recherche_est_rempli_au_save():
    food = make_food(name="Crème fraîche", brand="Élé & Vire")

    assert food.search_text == "creme fraiche ele & vire"


def test_le_texte_de_recherche_suit_les_modifications():
    food = make_food(name="Riz")

    food.name = "Riz complet"
    food.save()

    assert food.search_text == "riz complet"


# --- Contraintes --------------------------------------------------------------


def test_un_aliment_utilisateur_exige_un_proprietaire(active_user):
    with pytest.raises(IntegrityError):
        Food.objects.create(name="Ma recette", source=FoodSource.USER, owner=None)


def test_un_aliment_utilisateur_avec_proprietaire_est_accepte(active_user):
    food = make_food(name="Mon plat", source=FoodSource.USER, owner=active_user)

    assert food.pk


def test_un_identifiant_externe_est_unique_par_source():
    make_food(external_id="1000")

    with pytest.raises(IntegrityError):
        make_food(name="Doublon", external_id="1000")


def test_le_meme_identifiant_peut_exister_sur_deux_sources():
    make_food(external_id="1000", source=FoodSource.CIQUAL)
    other = make_food(name="Produit", external_id="1000", source=FoodSource.OFF)

    assert other.pk


def test_la_quantite_de_reference_doit_etre_positive():
    with pytest.raises(IntegrityError):
        make_food(reference_amount=Decimal("0"))


# --- Valeurs nutritionnelles --------------------------------------------------


def test_une_valeur_inconnue_reste_nulle():
    """Jamais de zéro artificiel (spec 01 §8)."""
    nutrition = FoodNutrition.objects.create(food=make_food(), energy_kcal=Decimal("120"))

    assert nutrition.vitamin_c_mg is None
    assert nutrition.energy_kcal == Decimal("120.000")


def test_glucides_nets():
    nutrition = FoodNutrition.objects.create(
        food=make_food(), carbohydrates_g=Decimal("20"), fiber_g=Decimal("5")
    )

    assert nutrition.net_carbs_g == Decimal("15.000")


def test_glucides_nets_inconnus_si_les_fibres_manquent():
    nutrition = FoodNutrition.objects.create(food=make_food(), carbohydrates_g=Decimal("20"))

    assert nutrition.net_carbs_g is None


# --- Portions -----------------------------------------------------------------


def test_une_portion_exige_au_moins_une_equivalence():
    with pytest.raises(IntegrityError):
        FoodPortion.objects.create(food=make_food(), name="1 tranche")


def test_une_portion_avec_equivalence_est_acceptee():
    portion = FoodPortion.objects.create(
        food=make_food(), name="1 tranche", gram_equivalent=Decimal("32")
    )

    assert portion.pk


def test_deux_portions_du_meme_nom_sur_le_meme_aliment_sont_refusees():
    food = make_food()
    FoodPortion.objects.create(food=food, name="1 pot", gram_equivalent=Decimal("125"))

    with pytest.raises(IntegrityError):
        FoodPortion.objects.create(food=food, name="1 pot", gram_equivalent=Decimal("125"))


def test_deux_utilisateurs_peuvent_nommer_leur_portion_pareil(active_user, other_user):
    food = make_food()
    FoodPortion.objects.create(
        food=food, owner=active_user, name="1 part", gram_equivalent=Decimal("100")
    )
    portion = FoodPortion.objects.create(
        food=food, owner=other_user, name="1 part", gram_equivalent=Decimal("150")
    )

    assert portion.pk


# --- Visibilité ---------------------------------------------------------------


def test_les_aliments_globaux_sont_visibles_par_tous(active_user):
    make_food(source=FoodSource.CIQUAL)

    assert Food.objects.visible_to(active_user).count() == 1


def test_un_aliment_prive_nest_visible_que_de_son_proprietaire(active_user, other_user):
    make_food(
        name="Secret",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.PRIVATE,
    )

    assert Food.objects.visible_to(active_user).count() == 0
    assert Food.objects.visible_to(other_user).count() == 1


def test_un_aliment_ouvert_a_tous_est_visible(active_user, other_user):
    make_food(
        name="Partagé",
        source=FoodSource.USER,
        owner=other_user,
        visibility=FoodVisibility.APP_USERS,
    )

    assert Food.objects.visible_to(active_user).count() == 1


def test_un_aliment_desactive_disparait(active_user):
    make_food(is_active=False)

    assert Food.objects.visible_to(active_user).count() == 0


def test_un_aliment_supprime_disparait(active_user):
    from django.utils import timezone

    make_food(deleted_at=timezone.now())

    assert Food.objects.visible_to(active_user).count() == 0


def test_seuls_ses_propres_aliments_sont_modifiables(active_user, other_user):
    make_food(source=FoodSource.CIQUAL)
    make_food(name="À moi", source=FoodSource.USER, owner=active_user)
    make_food(name="À l’autre", source=FoodSource.USER, owner=other_user)

    editable = Food.objects.editable_by(active_user)

    assert editable.count() == 1
    assert editable.get().name == "À moi"


def test_la_suppression_du_compte_emporte_ses_aliments(active_user):
    make_food(name="À moi", source=FoodSource.USER, owner=active_user)

    active_user.delete()

    assert Food.objects.count() == 0


def test_la_suppression_du_compte_epargne_les_aliments_globaux(active_user):
    make_food(source=FoodSource.CIQUAL)

    active_user.delete()

    assert Food.objects.count() == 1


def test_full_clean_accepte_un_aliment_valide(active_user):
    food = Food(name="Test", source=FoodSource.USER, owner=active_user)

    try:
        food.full_clean()
    except ValidationError as exc:  # pragma: no cover - diagnostic
        pytest.fail(f"validation inattendue : {exc}")
