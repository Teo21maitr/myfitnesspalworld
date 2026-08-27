"""Partages (spec 01 §17 et §18, spec 05 §2 et §7).

Toutes les erreurs de ce domaine se ressemblent : un accès accordé légitimement
puis conservé après la disparition de ce qui le justifiait. Aucune ne lève
d'exception ; ces tests sont le seul endroit où elles se voient.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import UserStatus
from nutrition.models import Food, FoodSource, FoodVisibility
from recipes.models import Recipe, RecipeVisibility, SavedMeal
from social.models import ResourceType, SharePermission, VisibilityType
from social.services import friends as friends_service
from social.services.sharing import can_read

from .conftest import client_for

pytestmark = pytest.mark.django_db

SHARES_URL = reverse("api-v1:shares:list")
RECEIVED_URL = reverse("api-v1:shares:received")


def befriend(first, second) -> None:
    request = friends_service.send_request(from_user=first, to_user=second)
    friends_service.accept(request=request, user=second)


def share(owner, target, resource_type, resource_id=None) -> SharePermission:
    return SharePermission.objects.create(
        owner=owner,
        target_user=target,
        resource_type=resource_type,
        resource_id=resource_id,
        visibility_type=(VisibilityType.SPECIFIC_USER if target else VisibilityType.APP_USERS),
    )


@pytest.fixture
def recipe(alice) -> Recipe:
    return Recipe.objects.create(
        owner=alice,
        name="Blanquette",
        servings=Decimal("4"),
        visibility=RecipeVisibility.SPECIFIC_USERS,
    )


# --- Révocation au retrait d'ami --------------------------------------------


def test_retirer_un_ami_revoque_les_partages_dans_les_deux_sens(alice, bob, recipe):
    befriend(alice, bob)
    share(alice, bob, ResourceType.RECIPE, recipe.id)
    share(bob, alice, ResourceType.DIARY)

    friends_service.remove_friend(user=alice, other=bob)

    assert SharePermission.objects.count() == 0


def test_lex_ami_ne_voit_plus_la_recette(alice, bob, recipe):
    befriend(alice, bob)
    share(alice, bob, ResourceType.RECIPE, recipe.id)
    assert Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()

    friends_service.remove_friend(user=alice, other=bob)

    assert not Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()


def test_lex_ami_ne_voit_plus_le_journal_ni_la_progression(alice, bob):
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)
    share(alice, bob, ResourceType.PROGRESS)

    friends_service.remove_friend(user=bob, other=alice)

    assert not can_read(bob, alice, ResourceType.DIARY)
    assert not can_read(bob, alice, ResourceType.PROGRESS)


def test_un_partage_global_survit_au_retrait_dami(alice, bob, recipe):
    """Il ne visait personne en particulier : l'amitié n'était pas son fondement."""
    befriend(alice, bob)
    share(alice, None, ResourceType.RECIPE, recipe.id)
    recipe.visibility = RecipeVisibility.APP_USERS
    recipe.save()

    friends_service.remove_friend(user=alice, other=bob)

    assert SharePermission.objects.count() == 1
    assert Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()


# --- Suspension --------------------------------------------------------------


def test_suspendre_un_compte_rend_ses_partages_inaccessibles(alice, bob, recipe):
    """`IsActiveAccount` ne contrôle que l'appelant (spec 05 §2)."""
    befriend(alice, bob)
    share(alice, bob, ResourceType.RECIPE, recipe.id)
    share(alice, bob, ResourceType.DIARY)

    alice.status = UserStatus.SUSPENDED
    alice.save()

    assert not Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()
    assert not can_read(bob, alice, ResourceType.DIARY)


def test_suspendre_ferme_aussi_les_partages_globaux(alice, bob, recipe):
    recipe.visibility = RecipeVisibility.APP_USERS
    recipe.save()
    assert Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()

    alice.status = UserStatus.SUSPENDED
    alice.save()

    assert not Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()


def test_reactiver_le_compte_retablit_les_partages(alice, bob, recipe):
    befriend(alice, bob)
    share(alice, bob, ResourceType.RECIPE, recipe.id)
    alice.status = UserStatus.SUSPENDED
    alice.save()

    alice.status = UserStatus.ACTIVE
    alice.save()

    assert Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()


# --- Confusion de type -------------------------------------------------------


def test_un_partage_de_recette_ne_donne_pas_acces_a_laliment_du_meme_numero(alice, bob, recipe):
    """Les identifiants sont propres à chaque table : la recette 42 et
    l'aliment 42 coexistent. L'identifiant est ici forcé pour le prouver."""
    befriend(alice, bob)
    twin = Food.objects.create(
        pk=recipe.id,
        source=FoodSource.USER,
        owner=alice,
        name="Granola maison",
        reference_amount=100,
        visibility=FoodVisibility.PRIVATE,
    )

    share(alice, bob, ResourceType.RECIPE, recipe.id)

    assert Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()
    assert not Food.objects.visible_to(bob).filter(pk=twin.pk).exists()


def test_un_partage_de_recette_ne_donne_pas_acces_au_repas_du_meme_numero(alice, bob, recipe):
    befriend(alice, bob)
    twin = SavedMeal.objects.create(pk=recipe.id, owner=alice, name="Mon déjeuner")

    share(alice, bob, ResourceType.RECIPE, recipe.id)

    assert not SavedMeal.objects.visible_to(bob).filter(pk=twin.pk).exists()


# --- Indépendance journal / progression --------------------------------------


def test_partager_son_journal_ne_partage_pas_sa_progression(alice, bob):
    """Les deux partages sont distincts (spec 01 §18)."""
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)

    assert can_read(bob, alice, ResourceType.DIARY)
    assert not can_read(bob, alice, ResourceType.PROGRESS)


def test_le_proprietaire_lit_toujours_ses_propres_donnees(alice):
    assert can_read(alice, alice, ResourceType.DIARY)


# --- API de partage ----------------------------------------------------------


def test_creation_dun_partage_cible(alice, bob, recipe):
    befriend(alice, bob)

    response = client_for(alice).post(
        SHARES_URL,
        {
            "resource_type": "recipe",
            "resource_id": recipe.id,
            "visibility": "specific_user",
            "target_user_id": bob.id,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["resource_name"] == "Blanquette"


def test_partager_avec_un_non_ami_est_refuse(alice, bob, recipe):
    response = client_for(alice).post(
        SHARES_URL,
        {
            "resource_type": "recipe",
            "resource_id": recipe.id,
            "visibility": "specific_user",
            "target_user_id": bob.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "target_user_id" in response.data["errors"]


def test_partager_la_ressource_dun_autre_est_refuse(alice, bob, carol):
    befriend(bob, carol)
    foreign = Recipe.objects.create(owner=alice, name="Pas à moi", servings=Decimal("1"))

    response = client_for(bob).post(
        SHARES_URL,
        {
            "resource_type": "recipe",
            "resource_id": foreign.id,
            "visibility": "specific_user",
            "target_user_id": carol.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "resource_id" in response.data["errors"]


def test_le_journal_se_partage_sans_identifiant(alice, bob):
    befriend(alice, bob)

    response = client_for(alice).post(
        SHARES_URL,
        {"resource_type": "diary", "visibility": "specific_user", "target_user_id": bob.id},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["resource_id"] is None


def test_un_identifiant_sur_le_journal_est_refuse(alice, bob):
    befriend(alice, bob)

    response = client_for(alice).post(
        SHARES_URL,
        {
            "resource_type": "diary",
            "resource_id": 1,
            "visibility": "specific_user",
            "target_user_id": bob.id,
        },
        format="json",
    )

    assert response.status_code == 400


def test_un_type_de_ressource_inconnu_est_refuse(alice, bob):
    befriend(alice, bob)

    response = client_for(alice).post(
        SHARES_URL,
        {
            "resource_type": "progress_photo",
            "visibility": "specific_user",
            "target_user_id": bob.id,
        },
        format="json",
    )

    # Les photos de progression ne sont partageables sous aucune forme
    # (spec 01 §20) : le type n'existe pas.
    assert response.status_code == 400


def test_un_partage_global_ne_vise_personne(alice, bob, recipe):
    befriend(alice, bob)

    response = client_for(alice).post(
        SHARES_URL,
        {
            "resource_type": "recipe",
            "resource_id": recipe.id,
            "visibility": "app_users",
            "target_user_id": bob.id,
        },
        format="json",
    )

    assert response.status_code == 400


def test_la_liste_recue_montre_ce_quon_ma_partage(alice, bob, recipe):
    befriend(alice, bob)
    share(alice, bob, ResourceType.RECIPE, recipe.id)

    rows = client_for(bob).get(RECEIVED_URL).data["results"]

    assert len(rows) == 1
    assert rows[0]["owner"]["username"] == "alice"
    assert rows[0]["resource_name"] == "Blanquette"


def test_la_liste_recue_ignore_un_proprietaire_suspendu(alice, bob, recipe):
    befriend(alice, bob)
    share(alice, bob, ResourceType.RECIPE, recipe.id)
    alice.status = UserStatus.SUSPENDED
    alice.save()

    assert client_for(bob).get(RECEIVED_URL).data["results"] == []


def test_revoquer_un_partage(alice, bob, recipe):
    befriend(alice, bob)
    permission = share(alice, bob, ResourceType.RECIPE, recipe.id)

    response = client_for(alice).delete(reverse("api-v1:shares:detail", args=[permission.id]))

    assert response.status_code == 204
    assert not Recipe.objects.visible_to(bob).filter(pk=recipe.pk).exists()


def test_on_ne_revoque_pas_le_partage_dun_autre(alice, bob, carol, recipe):
    befriend(alice, bob)
    permission = share(alice, bob, ResourceType.RECIPE, recipe.id)

    response = client_for(carol).delete(reverse("api-v1:shares:detail", args=[permission.id]))

    assert response.status_code == 404
    assert SharePermission.objects.filter(pk=permission.pk).exists()
