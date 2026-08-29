"""Qui m'a ouvert quoi (spec 01 §18, spec 04 §12).

Le piège de l'étape : **l'interface ne doit proposer que ce qui aboutit**. Les
boutons « Son journal » et « Sa progression » s'affichaient pour tous les amis,
et le backend répondait 404 — correctement, mais l'utilisateur voyait une
erreur là où il attendait une donnée.

La tentation était de déduire l'absence du 404. Ce serait une faute : le même
code couvre l'ami inexistant, le compte suspendu et l'incident serveur.
`opened_to` répond depuis les **propres accès de l'appelant**, la seule source
qui autorise une affirmation.

D'où la règle que ces tests protègent :

> `opened_to` et `can_read` disent toujours la même chose.

Un bouton affiché que `can_read` refuserait, c'est le défaut d'aujourd'hui à
l'envers ; un bouton caché que `can_read` accepterait cache une donnée reçue.
"""

import pytest

from accounts.models import UserStatus
from social.models import ResourceType, SharePermission, VisibilityType
from social.services import friends as friends_service
from social.services.sharing import can_read, opened_to

pytestmark = pytest.mark.django_db


def befriend(first, second) -> None:
    request = friends_service.send_request(from_user=first, to_user=second)
    friends_service.accept(request=request, user=second)


@pytest.fixture
def recipe_of_alice(alice):
    from decimal import Decimal

    from recipes.models import Recipe, RecipeVisibility

    return Recipe.objects.create(
        owner=alice,
        name="Blanquette",
        servings=Decimal("4"),
        visibility=RecipeVisibility.SPECIFIC_USERS,
    )


def share(owner, target, resource_type) -> SharePermission:
    return SharePermission.objects.create(
        owner=owner,
        target_user=target,
        resource_type=resource_type,
        visibility_type=(VisibilityType.SPECIFIC_USER if target else VisibilityType.APP_USERS),
    )


class TestOpenedAgreesWithCanRead:
    """Les deux réponses viennent des mêmes permissions : elles ne peuvent pas diverger."""

    @pytest.mark.parametrize("resource_type", [ResourceType.DIARY, ResourceType.PROGRESS])
    def test_un_partage_nomme(self, alice, bob, resource_type):
        befriend(alice, bob)
        share(alice, bob, resource_type)

        assert alice.id in opened_to(bob)[resource_type]
        assert can_read(bob, alice, resource_type)

    def test_un_partage_ouvert_a_tous(self, alice, bob):
        """Sans amitié : un partage global ne vise personne, et vaut pour tous."""
        share(alice, None, ResourceType.DIARY)

        assert alice.id in opened_to(bob)[ResourceType.DIARY]
        assert can_read(bob, alice, ResourceType.DIARY)

    def test_aucun_partage(self, alice, bob):
        befriend(alice, bob)

        assert opened_to(bob)[ResourceType.DIARY] == set()
        assert not can_read(bob, alice, ResourceType.DIARY)

    def test_un_proprietaire_suspendu_n_ouvre_plus_rien(self, alice, bob):
        """Suspendre un compte rend ses partages inaccessibles (spec 05 §2)."""
        befriend(alice, bob)
        share(alice, bob, ResourceType.DIARY)
        alice.status = UserStatus.SUSPENDED
        alice.save(update_fields=["status"])

        assert opened_to(bob)[ResourceType.DIARY] == set()
        assert not can_read(bob, alice, ResourceType.DIARY)


class TestScope:
    def test_le_journal_et_la_progression_restent_distincts(self, alice, bob):
        """Ouvrir l'un n'ouvre pas l'autre (spec 01 §18)."""
        befriend(alice, bob)
        share(alice, bob, ResourceType.DIARY)

        opened = opened_to(bob)

        assert opened[ResourceType.DIARY] == {alice.id}
        assert opened[ResourceType.PROGRESS] == set()

    def test_un_partage_vers_quelqu_un_d_autre_ne_me_concerne_pas(self, alice, bob, carol):
        befriend(alice, carol)
        share(alice, carol, ResourceType.DIARY)

        assert opened_to(bob)[ResourceType.DIARY] == set()

    def test_les_deux_types_sont_toujours_presents(self, alice):
        """Une clé absente ferait planter l'appelant plutôt que masquer un bouton."""
        opened = opened_to(alice)

        assert set(opened) == {ResourceType.DIARY, ResourceType.PROGRESS}

    def test_un_partage_de_recette_n_ouvre_pas_le_journal(self, alice, bob, recipe_of_alice):
        """Les identifiants sont propres à chaque table : le type fait partie du filtre."""
        befriend(alice, bob)
        SharePermission.objects.create(
            owner=alice,
            target_user=bob,
            resource_type=ResourceType.RECIPE,
            resource_id=recipe_of_alice.id,
            visibility_type=VisibilityType.SPECIFIC_USER,
        )

        assert opened_to(bob)[ResourceType.DIARY] == set()

    def test_une_seule_requete_quel_que_soit_le_nombre_d_amis(
        self, alice, bob, carol, django_assert_num_queries
    ):
        share(alice, None, ResourceType.DIARY)
        share(carol, None, ResourceType.PROGRESS)

        with django_assert_num_queries(1):
            opened_to(bob)


class TestFriendsEndpoint:
    """`GET /friends/` porte les deux drapeaux (spec 04 §12)."""

    def url(self):
        from django.urls import reverse

        return reverse("api-v1:friends:list")

    def test_un_ami_qui_a_partage_porte_ses_drapeaux(self, alice, bob):
        from .conftest import client_for

        befriend(alice, bob)
        share(alice, bob, ResourceType.DIARY)

        response = client_for(bob).get(self.url())

        assert response.status_code == 200
        row = response.json()["results"][0]
        assert row["username"] == "alice"
        assert row["shares_diary"] is True
        assert row["shares_progress"] is False

    def test_un_ami_qui_n_a_rien_partage_le_dit(self, alice, bob):
        from .conftest import client_for

        befriend(alice, bob)

        row = client_for(bob).get(self.url()).json()["results"][0]

        assert row["shares_diary"] is False
        assert row["shares_progress"] is False

    def test_la_recherche_n_expose_pas_ces_drapeaux(self, alice, bob):
        """`/users/search/` porte sur des inconnus : leurs partages ne le regardent pas."""
        from django.urls import reverse

        from .conftest import client_for

        share(alice, None, ResourceType.DIARY)

        response = client_for(bob).get(reverse("api-v1:users:search"), {"q": "ali"})

        assert response.status_code == 200
        assert "shares_diary" not in response.json()["results"][0]
