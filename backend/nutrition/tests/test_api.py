"""API des objectifs nutritionnels et de l'onboarding (spec 04 §2)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ActivityLevel, GoalType, SexForCalculation, User, UserStatus
from accounts.services.sessions import build_refresh_token
from nutrition.models import NutritionGoal
from nutrition.services import goals as goals_service
from progress.models import WeightEntry

pytestmark = pytest.mark.django_db

CALCULATE_URL = reverse("api-v1:nutrition:goals-calculate")
ONBOARDING_URL = reverse("api-v1:nutrition:onboarding")
GOALS_URL = reverse("api-v1:nutrition:goals")
CURRENT_URL = reverse("api-v1:nutrition:goals-current")
PROFILE_URL = reverse("api-v1:profile:profile")

ADULT_BIRTH_DATE = "1996-01-01"

CALCULATION_PAYLOAD = {
    "birth_date": ADULT_BIRTH_DATE,
    "sex_for_calculation": SexForCalculation.MALE,
    "height_cm": "180.0",
    "weight_kg": "80.00",
    "activity_level": ActivityLevel.MODERATELY_ACTIVE,
    "goal_type": GoalType.LOSS,
    "goal_rate_kg_per_week": "0.50",
    "target_weight_kg": "75.00",
}

ONBOARDING_PAYLOAD = {
    **CALCULATION_PAYLOAD,
    "daily_calories": "2209",
    "protein_g": "166",
    "carbs_g": "221",
    "fat_g": "74",
}

GOAL_VALUES = {
    "daily_calories": Decimal("2000"),
    "protein_g": Decimal("150"),
    "carbs_g": Decimal("200"),
    "fat_g": Decimal("67"),
}


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


# --- Calcul -------------------------------------------------------------------


def test_le_calcul_exige_une_authentification(api_client):
    assert api_client.post(CALCULATE_URL, CALCULATION_PAYLOAD).status_code == 401


def test_le_calcul_renvoie_les_valeurs_et_la_mention(auth_client):
    response = auth_client.post(CALCULATE_URL, CALCULATION_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["bmr"] == "1780.00"
    assert body["daily_calories"] == "2209.00"
    assert "recommandation médicale" in body["notice"]
    assert body["warnings"] == []


def test_le_calcul_ne_persiste_rien(auth_client, active_user):
    auth_client.post(CALCULATE_URL, CALCULATION_PAYLOAD)

    assert NutritionGoal.objects.filter(user=active_user).count() == 0
    active_user.profile.refresh_from_db()
    assert active_user.profile.birth_date is None


def test_le_calcul_remonte_les_avertissements(auth_client):
    response = auth_client.post(
        CALCULATE_URL,
        {**CALCULATION_PAYLOAD, "goal_rate_kg_per_week": "1.50", "target_weight_kg": "70.00"},
    )

    assert response.status_code == 200
    # Avertissement non bloquant : la valeur est bien renvoyée (spec 01 §3).
    assert response.json()["warnings"]
    assert response.json()["daily_calories"]


def test_un_mineur_est_refuse(auth_client):
    minor_birth_date = (date.today() - timedelta(days=365 * 15)).isoformat()

    response = auth_client.post(
        CALCULATE_URL, {**CALCULATION_PAYLOAD, "birth_date": minor_birth_date}
    )

    assert response.status_code == 400
    assert "birth_date" in response.json()["errors"]


def test_une_date_de_naissance_future_est_refusee(auth_client):
    future = (date.today() + timedelta(days=1)).isoformat()

    response = auth_client.post(CALCULATE_URL, {**CALCULATION_PAYLOAD, "birth_date": future})

    assert response.status_code == 400


def test_un_objectif_de_perte_avec_poids_cible_superieur_est_refuse(auth_client):
    response = auth_client.post(CALCULATE_URL, {**CALCULATION_PAYLOAD, "target_weight_kg": "90.00"})

    assert response.status_code == 400
    assert "target_weight_kg" in response.json()["errors"]


def test_un_objectif_de_prise_avec_poids_cible_inferieur_est_refuse(auth_client):
    response = auth_client.post(
        CALCULATE_URL,
        {**CALCULATION_PAYLOAD, "goal_type": GoalType.GAIN, "target_weight_kg": "70.00"},
    )

    assert response.status_code == 400


# --- Onboarding ---------------------------------------------------------------


def test_l_onboarding_renseigne_profil_poids_et_objectif(auth_client, active_user):
    response = auth_client.post(ONBOARDING_URL, ONBOARDING_PAYLOAD)

    assert response.status_code == 201

    active_user.profile.refresh_from_db()
    assert active_user.profile.onboarding_completed is True
    assert active_user.profile.birth_date == date(1996, 1, 1)
    assert active_user.profile.height_cm == Decimal("180.0")

    weight = WeightEntry.objects.get(user=active_user)
    assert weight.weight_kg == Decimal("80.00")
    assert weight.date == date.today()

    goal = NutritionGoal.objects.get(user=active_user)
    assert goal.daily_calories == Decimal("2209.00")
    assert goal.start_date == date.today()


def test_l_onboarding_accepte_des_valeurs_remplacees_manuellement(auth_client, active_user):
    """L'utilisateur peut remplacer les calories proposées (spec 01 §2)."""
    response = auth_client.post(
        ONBOARDING_URL,
        {**ONBOARDING_PAYLOAD, "daily_calories": "1900", "calories_source": "manual"},
    )

    assert response.status_code == 201
    goal = NutritionGoal.objects.get(user=active_user)
    assert goal.daily_calories == Decimal("1900.00")
    assert goal.calories_source == "manual"


def test_l_onboarding_ne_peut_pas_etre_rejoue(auth_client):
    auth_client.post(ONBOARDING_URL, ONBOARDING_PAYLOAD)

    response = auth_client.post(ONBOARDING_URL, ONBOARDING_PAYLOAD)

    assert response.status_code == 400
    assert response.json()["code"] == "onboarding_already_completed"


def test_un_onboarding_invalide_n_ecrit_rien(auth_client, active_user):
    """Transaction : un payload refusé ne laisse aucune trace."""
    response = auth_client.post(ONBOARDING_URL, {**ONBOARDING_PAYLOAD, "daily_calories": "-100"})

    assert response.status_code == 400
    active_user.profile.refresh_from_db()
    assert active_user.profile.onboarding_completed is False
    assert WeightEntry.objects.filter(user=active_user).count() == 0
    assert NutritionGoal.objects.filter(user=active_user).count() == 0


def test_l_onboarding_exige_une_authentification(api_client):
    assert api_client.post(ONBOARDING_URL, ONBOARDING_PAYLOAD).status_code == 401


# --- Objectifs ----------------------------------------------------------------


def test_liste_des_objectifs_par_ordre_antichronologique(auth_client, active_user):
    goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **GOAL_VALUES)
    goals_service.create_goal(active_user, start_date=date(2026, 3, 1), **GOAL_VALUES)

    body = auth_client.get(GOALS_URL).json()

    assert body["count"] == 2
    assert body["results"][0]["start_date"] == "2026-03-01"
    assert body["results"][0]["is_current"] is True
    assert body["results"][1]["is_current"] is False


def test_creation_dun_objectif_par_l_api(auth_client, active_user):
    response = auth_client.post(
        GOALS_URL,
        {
            "daily_calories": "1800",
            "protein_g": "140",
            "carbs_g": "180",
            "fat_g": "60",
            "fiber_g": "30",
        },
    )

    assert response.status_code == 201
    goal = NutritionGoal.objects.get(user=active_user)
    assert goal.daily_calories == Decimal("1800.00")
    assert goal.net_carbs_g == Decimal("150.00")


def test_lecart_macros_calories_est_expose(auth_client, active_user):
    goals_service.create_goal(
        active_user,
        start_date=date.today(),
        daily_calories=Decimal("2000"),
        protein_g=Decimal("150"),
        carbs_g=Decimal("200"),
        fat_g=Decimal("100"),
    )

    body = auth_client.get(GOALS_URL).json()

    # Les calories font foi : l'écart est signalé, pas corrigé (spec 01 §4).
    assert Decimal(body["results"][0]["macro_calories_gap"]) == Decimal("300")
    assert body["results"][0]["daily_calories"] == "2000.00"


def test_objectif_courant_et_valeurs_du_jour(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    goals_service.set_day_override(goal, date.today().weekday(), daily_calories=Decimal("2400"))

    body = auth_client.get(CURRENT_URL).json()

    assert body["goal"]["id"] == goal.pk
    assert Decimal(body["today"]["daily_calories"]) == Decimal("2400")


def test_les_valeurs_du_jour_sont_serialisees_comme_lobjectif(auth_client, active_user):
    """Même format des deux côtés.

    Sans cela, le frontend comparant `today` et `goal` conclurait à tort
    qu'une surcharge est active.
    """
    goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)

    body = auth_client.get(CURRENT_URL).json()

    assert body["today"]["daily_calories"] == body["goal"]["daily_calories"]
    assert isinstance(body["today"]["daily_calories"], str)
    assert body["today"]["protein_g"] == body["goal"]["protein_g"]


def test_les_valeurs_du_jour_different_avec_une_surcharge(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    goals_service.set_day_override(goal, date.today().weekday(), daily_calories=Decimal("2400"))

    body = auth_client.get(CURRENT_URL).json()

    assert body["today"]["daily_calories"] != body["goal"]["daily_calories"]
    # Les champs non surchargés restent identiques.
    assert body["today"]["protein_g"] == body["goal"]["protein_g"]


def test_objectif_courant_absent(auth_client):
    response = auth_client.get(CURRENT_URL)

    assert response.status_code == 404


def test_modification_dun_objectif(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-detail", args=[goal.pk])

    response = auth_client.patch(url, {"daily_calories": "1750"})

    assert response.status_code == 200
    goal.refresh_from_db()
    assert goal.daily_calories == Decimal("1750.00")


def test_la_periode_dun_objectif_nest_pas_modifiable(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date(2026, 1, 1), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-detail", args=[goal.pk])

    auth_client.patch(url, {"start_date": "2020-01-01", "end_date": "2030-01-01"})

    goal.refresh_from_db()
    assert goal.start_date == date(2026, 1, 1)
    assert goal.end_date is None


# --- Surcharges ---------------------------------------------------------------


def test_pose_dune_surcharge(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-override", args=[goal.pk, 5])

    response = auth_client.put(url, {"daily_calories": "2500", "protein_g": "160"})

    assert response.status_code == 200
    assert response.json()["weekday_label"] == "samedi"
    assert goal.day_overrides.get(weekday=5).daily_calories == Decimal("2500")


def test_une_surcharge_est_remplacable(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-override", args=[goal.pk, 5])

    auth_client.put(url, {"daily_calories": "2500"})
    auth_client.put(url, {"daily_calories": "2600"})

    assert goal.day_overrides.count() == 1


def test_suppression_dune_surcharge(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-override", args=[goal.pk, 5])
    auth_client.put(url, {"daily_calories": "2500"})

    assert auth_client.delete(url).status_code == 204
    assert goal.day_overrides.count() == 0


def test_un_jour_hors_plage_est_refuse_par_lapi(auth_client, active_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-override", args=[goal.pk, 9])

    assert auth_client.put(url, {"daily_calories": "2500"}).status_code == 400


# --- Isolation entre utilisateurs ---------------------------------------------


def test_un_utilisateur_ne_voit_que_ses_objectifs(active_user, other_user):
    goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)

    body = client_for(other_user).get(GOALS_URL).json()

    assert body["count"] == 0


def test_un_utilisateur_ne_peut_pas_lire_lobjectif_dun_autre(active_user, other_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-detail", args=[goal.pk])

    assert client_for(other_user).get(url).status_code == 404


def test_un_utilisateur_ne_peut_pas_modifier_lobjectif_dun_autre(active_user, other_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-detail", args=[goal.pk])

    assert client_for(other_user).patch(url, {"daily_calories": "500"}).status_code == 404
    goal.refresh_from_db()
    assert goal.daily_calories == Decimal("2000.00")


def test_un_utilisateur_ne_peut_pas_surcharger_lobjectif_dun_autre(active_user, other_user):
    goal = goals_service.create_goal(active_user, start_date=date.today(), **GOAL_VALUES)
    url = reverse("api-v1:nutrition:goal-override", args=[goal.pk, 2])

    assert client_for(other_user).put(url, {"daily_calories": "9999"}).status_code == 404
    assert goal.day_overrides.count() == 0


def test_un_compte_suspendu_na_pas_acces_aux_objectifs(active_user):
    client = client_for(active_user)
    active_user.status = UserStatus.SUSPENDED
    active_user.save()

    assert client.get(GOALS_URL).status_code == 401


# --- Profil nutritionnel ------------------------------------------------------


def test_le_profil_expose_les_champs_nutritionnels(auth_client):
    body = auth_client.get(PROFILE_URL).json()

    assert "profile" in body
    assert body["profile"]["birth_date"] is None
    assert body["profile"]["onboarding_completed"] is False


def test_les_champs_nutritionnels_sont_modifiables(auth_client, active_user):
    response = auth_client.patch(
        PROFILE_URL,
        {"profile": {"height_cm": "182.0", "activity_level": ActivityLevel.VERY_ACTIVE}},
        format="json",
    )

    assert response.status_code == 200
    active_user.profile.refresh_from_db()
    assert active_user.profile.height_cm == Decimal("182.0")
    assert active_user.profile.activity_level == ActivityLevel.VERY_ACTIVE


def test_onboarding_completed_nest_pas_modifiable_par_le_profil(auth_client, active_user):
    auth_client.patch(PROFILE_URL, {"profile": {"onboarding_completed": True}}, format="json")

    active_user.profile.refresh_from_db()
    assert active_user.profile.onboarding_completed is False


def test_le_profil_refuse_un_mineur(auth_client):
    minor = (date.today() - timedelta(days=365 * 10)).isoformat()

    response = auth_client.patch(PROFILE_URL, {"profile": {"birth_date": minor}}, format="json")

    assert response.status_code == 400
