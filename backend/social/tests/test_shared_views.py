"""Consultation partagée du journal et de la progression (spec 05 §8 et §9).

Ces routes ne font que lire. Elles sont distinctes de celles du propriétaire :
une route qui servirait « mes données » ou « celles d'un autre » selon un
paramètre est la façon canonique de fabriquer un IDOR.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from diary.models import DiaryEntry
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import Food, FoodNutrition, FoodSource
from progress.models import WeightEntry
from social.models import ResourceType, SharePermission, VisibilityType
from social.services import friends as friends_service

from .conftest import client_for

pytestmark = pytest.mark.django_db

SHARED_DIARY_URL = reverse("api-v1:shared:diary")
SHARED_CHARTS_URL = reverse("api-v1:shared:progress-charts")
SHARED_WEIGHT_URL = reverse("api-v1:shared:progress-weight")

TODAY = date(2026, 8, 26)


def befriend(first, second) -> None:
    request = friends_service.send_request(from_user=first, to_user=second)
    friends_service.accept(request=request, user=second)


def share(owner, target, resource_type) -> SharePermission:
    return SharePermission.objects.create(
        owner=owner,
        target_user=target,
        resource_type=resource_type,
        visibility_type=VisibilityType.SPECIFIC_USER,
    )


@pytest.fixture
def alice_journal(alice) -> DiaryEntry:
    """Une journée d'Alice avec 400 kcal."""
    food = Food.objects.create(
        source=FoodSource.CIQUAL, external_id="1", name="Poulet", reference_amount=100
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("200"))

    return entries_service.create_food_entry(
        user=alice,
        food=food,
        day=TODAY,
        meal_type=meal_types_for(alice).first(),
        quantity=Decimal("200"),
        unit_label="g",
        consumed_at=timezone.make_aware(timezone.datetime(2026, 8, 26, 12, 0)),
    )


# --- Journal ----------------------------------------------------------------


def test_un_ami_lit_le_journal_partage(alice, bob, alice_journal):
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)

    response = client_for(bob).get(
        SHARED_DIARY_URL, {"user_id": alice.id, "date": TODAY.isoformat()}
    )

    assert response.status_code == 200
    assert response.data["totals"]["energy_kcal"] == "400.000"


def test_sans_partage_le_journal_est_introuvable(alice, bob, alice_journal):
    """404 plutôt que 403 : dire qu'une ressource existe renseigne déjà."""
    befriend(alice, bob)

    response = client_for(bob).get(
        SHARED_DIARY_URL, {"user_id": alice.id, "date": TODAY.isoformat()}
    )

    assert response.status_code == 404


def test_sans_identifiant_le_journal_est_introuvable(alice, bob):
    assert client_for(bob).get(SHARED_DIARY_URL).status_code == 404


def test_un_compte_suspendu_ferme_son_journal_partage(alice, bob, alice_journal):
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)
    alice.status = "SUSPENDED"
    alice.save()

    response = client_for(bob).get(
        SHARED_DIARY_URL, {"user_id": alice.id, "date": TODAY.isoformat()}
    )

    assert response.status_code == 404


def test_le_journal_partage_montre_les_totaux_du_proprietaire(alice, bob, alice_journal):
    """Et non ceux de celui qui regarde."""
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)

    mine = client_for(bob).get(reverse("api-v1:diary:day"), {"date": TODAY.isoformat()})
    theirs = client_for(bob).get(SHARED_DIARY_URL, {"user_id": alice.id, "date": TODAY.isoformat()})

    assert mine.data["totals"]["energy_kcal"] == "0.000"
    assert theirs.data["totals"]["energy_kcal"] == "400.000"


def test_aucune_ecriture_nexiste_sous_shared(alice, bob, alice_journal):
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)
    client = client_for(bob)
    params = {"user_id": alice.id}

    assert client.post(SHARED_DIARY_URL, params, format="json").status_code == 405
    assert client.patch(SHARED_DIARY_URL, params, format="json").status_code == 405
    assert client.delete(SHARED_DIARY_URL, params, format="json").status_code == 405


def test_une_entree_dun_ami_reste_inaccessible_aux_routes_normales(alice, bob, alice_journal):
    """Le partage donne à lire, jamais à écrire (spec 05 §8)."""
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)
    url = reverse("api-v1:diary:entry-detail", args=[alice_journal.id])

    client = client_for(bob)
    assert client.patch(url, {"quantity": "999"}, format="json").status_code == 404
    assert client.delete(url).status_code == 404

    alice_journal.refresh_from_db()
    assert alice_journal.quantity == Decimal("200.000")


# --- Progression -------------------------------------------------------------


def test_un_ami_lit_la_courbe_partagee(alice, bob):
    befriend(alice, bob)
    share(alice, bob, ResourceType.PROGRESS)
    WeightEntry.objects.create(user=alice, date=TODAY, weight_kg=Decimal("78"))

    response = client_for(bob).get(
        SHARED_CHARTS_URL,
        {"user_id": alice.id, "from": "2026-08-01", "to": TODAY.isoformat()},
    )

    assert response.status_code == 200
    assert [point["value"] for point in response.data["points"]] == ["78.00"]


def test_un_ami_lit_les_pesees_partagees(alice, bob):
    befriend(alice, bob)
    share(alice, bob, ResourceType.PROGRESS)
    WeightEntry.objects.create(user=alice, date=TODAY, weight_kg=Decimal("78"))

    response = client_for(bob).get(SHARED_WEIGHT_URL, {"user_id": alice.id})

    assert response.status_code == 200
    assert len(response.data["results"]) == 1


def test_le_partage_du_journal_nouvre_pas_la_progression(alice, bob):
    """Les deux partages sont distincts (spec 01 §18)."""
    befriend(alice, bob)
    share(alice, bob, ResourceType.DIARY)

    assert client_for(bob).get(SHARED_CHARTS_URL, {"user_id": alice.id}).status_code == 404


def test_le_partage_de_la_progression_nouvre_pas_le_journal(alice, bob, alice_journal):
    befriend(alice, bob)
    share(alice, bob, ResourceType.PROGRESS)

    response = client_for(bob).get(
        SHARED_DIARY_URL, {"user_id": alice.id, "date": TODAY.isoformat()}
    )

    assert response.status_code == 404


def test_la_consultation_partagee_exige_une_authentification(api_client, alice):
    assert api_client.get(SHARED_DIARY_URL, {"user_id": alice.id}).status_code == 401
