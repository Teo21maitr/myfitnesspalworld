"""Règles métier du modèle utilisateur (spec 01 §1, spec 05 §2)."""

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError

from accounts.models import UserStatus, normalize_username

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_create_user_normalise_le_username():
    user = User.objects.create_user(username="TeoMaitrot", password="un-mot-de-passe-1")

    assert user.username == "TeoMaitrot"
    assert user.normalized_username == "teomaitrot"


def test_username_unique_insensible_a_la_casse():
    User.objects.create_user(username="teo", password="un-mot-de-passe-1")

    with pytest.raises(ValidationError):
        User.objects.create_user(username="TEO", password="un-mot-de-passe-2")


def test_username_reste_modifiable_en_conservant_la_normalisation():
    user = User.objects.create_user(username="teo", password="un-mot-de-passe-1")

    user.username = "Teo.Maitrot"
    user.save()
    user.refresh_from_db()

    assert user.normalized_username == "teo.maitrot"


def test_nouvel_utilisateur_est_pending_par_defaut():
    user = User.objects.create_user(username="teo", password="un-mot-de-passe-1")

    assert user.status == UserStatus.PENDING
    assert user.is_active is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (UserStatus.ACTIVE, True),
        (UserStatus.PENDING, False),
        (UserStatus.SUSPENDED, False),
    ],
)
def test_is_active_derive_du_statut(status, expected):
    user = User.objects.create_user(username="teo", password="un-mot-de-passe-1", status=status)

    assert user.is_active is expected


def test_email_est_facultatif():
    user = User.objects.create_user(username="teo", password="un-mot-de-passe-1")

    assert user.email is None


def test_create_superuser_est_actif_et_staff():
    user = User.objects.create_superuser(username="admin", password="un-mot-de-passe-1")

    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True


def test_create_superuser_refuse_un_statut_non_actif():
    with pytest.raises(ValueError, match="ACTIVE"):
        User.objects.create_superuser(
            username="admin",
            password="un-mot-de-passe-1",
            status=UserStatus.SUSPENDED,
        )


def test_get_by_natural_key_est_insensible_a_la_casse():
    user = User.objects.create_user(username="Teo", password="un-mot-de-passe-1")

    assert User.objects.get_by_natural_key("tEO") == user


def test_authentification_insensible_a_la_casse_pour_un_compte_actif():
    User.objects.create_user(username="Teo", password="un-mot-de-passe-1", status=UserStatus.ACTIVE)

    assert authenticate(username="teo", password="un-mot-de-passe-1") is not None


@pytest.mark.parametrize("status", [UserStatus.PENDING, UserStatus.SUSPENDED])
def test_un_compte_non_actif_ne_peut_pas_se_connecter(status):
    User.objects.create_user(username="teo", password="un-mot-de-passe-1", status=status)

    assert authenticate(username="teo", password="un-mot-de-passe-1") is None


def test_username_vide_est_refuse():
    with pytest.raises(ValueError, match="obligatoire"):
        User.objects.create_user(username="", password="un-mot-de-passe-1")


def test_normalize_username_supprime_les_espaces_et_la_casse():
    assert normalize_username("  Teo  ") == "teo"


def test_full_name_retombe_sur_le_username():
    user = User.objects.create_user(username="teo", password="un-mot-de-passe-1")
    assert user.full_name == "teo"

    user.first_name = "Téo"
    user.last_name = "Maitrot"
    assert user.full_name == "Téo Maitrot"
