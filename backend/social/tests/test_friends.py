"""Demandes d'amitié et amitiés (spec 01 §17, spec 04 §12)."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from social.models import FriendRequest, FriendRequestStatus, Friendship
from social.services import friends as friends_service
from social.services.sharing import are_friends

from .conftest import client_for

pytestmark = pytest.mark.django_db

SEARCH_URL = reverse("api-v1:users:search")
FRIENDS_URL = reverse("api-v1:friends:list")
REQUESTS_URL = reverse("api-v1:friend-requests:list")


def befriend(first, second) -> None:
    request = friends_service.send_request(from_user=first, to_user=second)
    friends_service.accept(request=request, user=second)


# --- Amitié -----------------------------------------------------------------


def test_accepter_cree_une_amitie(alice, bob):
    request = friends_service.send_request(from_user=alice, to_user=bob)
    friends_service.accept(request=request, user=bob)

    assert are_friends(alice, bob)
    assert are_friends(bob, alice)


def test_lordre_canonique_ne_depend_pas_du_sens_de_la_demande(alice, bob):
    """Sans forme unique, A→B et B→A coexisteraient."""
    friends_service.accept(
        request=friends_service.send_request(from_user=bob, to_user=alice), user=alice
    )

    friendship = Friendship.objects.get()
    assert friendship.user_1_id < friendship.user_2_id


def test_pas_de_doublon_damitie(alice, bob):
    befriend(alice, bob)

    with pytest.raises(ValidationError):
        friends_service.send_request(from_user=alice, to_user=bob)

    assert Friendship.objects.count() == 1


def test_sajouter_soi_meme_est_refuse(alice):
    with pytest.raises(ValidationError):
        friends_service.send_request(from_user=alice, to_user=alice)


def test_une_seconde_demande_en_attente_est_refusee(alice, bob):
    friends_service.send_request(from_user=alice, to_user=bob)

    with pytest.raises(ValidationError):
        friends_service.send_request(from_user=alice, to_user=bob)


def test_une_demande_croisee_vaut_acceptation(alice, bob):
    """Demander la même chose que l'autre, c'est être d'accord."""
    friends_service.send_request(from_user=alice, to_user=bob)
    friends_service.send_request(from_user=bob, to_user=alice)

    assert are_friends(alice, bob)


def test_on_ne_peut_pas_accepter_sa_propre_demande(alice, bob):
    request = friends_service.send_request(from_user=alice, to_user=bob)

    with pytest.raises(ValidationError):
        friends_service.accept(request=request, user=alice)

    assert not are_friends(alice, bob)


def test_refuser_ne_cree_pas_damitie(alice, bob):
    request = friends_service.send_request(from_user=alice, to_user=bob)
    friends_service.reject(request=request, user=bob)

    assert not are_friends(alice, bob)
    assert FriendRequest.objects.get().status == FriendRequestStatus.REJECTED


def test_une_demande_traitee_ne_se_retraite_pas(alice, bob):
    request = friends_service.send_request(from_user=alice, to_user=bob)
    friends_service.accept(request=request, user=bob)

    with pytest.raises(ValidationError):
        friends_service.reject(request=request, user=bob)


def test_retirer_un_ami_supprime_lamitie(alice, bob):
    befriend(alice, bob)

    friends_service.remove_friend(user=alice, other=bob)

    assert not are_friends(alice, bob)


def test_retirer_quelquun_qui_nest_pas_ami_est_refuse(alice, bob):
    with pytest.raises(ValidationError):
        friends_service.remove_friend(user=alice, other=bob)


# --- Recherche --------------------------------------------------------------


def test_recherche_partielle_insensible_a_la_casse(alice, bob):
    results = friends_service.search_users(user=alice, query="BO")

    assert list(results) == [bob]


def test_la_recherche_ne_se_renvoie_pas_soi_meme(alice):
    assert list(friends_service.search_users(user=alice, query="ali")) == []


def test_la_recherche_exige_deux_caracteres(alice, bob):
    assert list(friends_service.search_users(user=alice, query="b")) == []


def test_la_recherche_ignore_les_comptes_inactifs(alice, bob):
    bob.status = "SUSPENDED"
    bob.save()

    assert list(friends_service.search_users(user=alice, query="bob")) == []


def test_la_recherche_ne_porte_pas_sur_lemail(alice, bob):
    """La spec 01 §1 exclut l'email de la recherche sociale."""
    bob.email = "secret@example.com"
    bob.save()

    assert list(friends_service.search_users(user=alice, query="secret")) == []


# --- API --------------------------------------------------------------------


def test_lapi_liste_les_amis(alice, bob):
    befriend(alice, bob)

    response = client_for(alice).get(FRIENDS_URL)

    assert response.status_code == 200
    assert [row["username"] for row in response.data["results"]] == ["bob"]


def test_lapi_ne_revele_pas_lemail(alice, bob):
    befriend(alice, bob)

    row = client_for(alice).get(FRIENDS_URL).data["results"][0]

    assert set(row) == {"id", "username", "first_name", "last_name"}


def test_lapi_envoie_et_accepte_une_demande(alice, bob):
    created = client_for(alice).post(REQUESTS_URL, {"to_user_id": bob.id}, format="json")
    assert created.status_code == 201
    assert created.data["direction"] == "sent"

    accepted = client_for(bob).post(
        reverse("api-v1:friend-requests:accept", args=[created.data["id"]])
    )

    assert accepted.status_code == 204
    assert are_friends(alice, bob)


def test_une_demande_adressee_a_un_autre_nest_pas_atteignable(alice, bob, carol):
    request = friends_service.send_request(from_user=alice, to_user=bob)

    response = client_for(carol).post(reverse("api-v1:friend-requests:accept", args=[request.id]))

    assert response.status_code == 404
    assert not are_friends(alice, bob)


def test_la_liste_des_demandes_montre_les_deux_sens(alice, bob, carol):
    friends_service.send_request(from_user=alice, to_user=bob)
    friends_service.send_request(from_user=carol, to_user=alice)

    rows = client_for(alice).get(REQUESTS_URL).data["results"]

    assert {row["direction"] for row in rows} == {"sent", "received"}


def test_le_social_exige_une_authentification(api_client):
    assert api_client.get(SEARCH_URL).status_code == 401
    assert api_client.get(FRIENDS_URL).status_code == 401
