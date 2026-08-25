"""Administration du modèle User personnalisé (spec 05 §4).

Le modèle remplace `is_active` par une propriété dérivée de `status` et
utilise un formulaire de création dédié : ces tests garantissent que les
pages d'admin continuent de s'afficher.
"""

import pytest
from django.urls import reverse

from accounts.models import User, UserStatus


@pytest.fixture
def admin_client_mfp(client, db):
    admin = User.objects.create_superuser(username="admin", password="mot-de-passe-admin-1")
    client.force_login(admin)
    return client, admin


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["admin:index", "admin:accounts_user_changelist", "admin:accounts_user_add"],
)
def test_les_pages_dadmin_saffichent(admin_client_mfp, url_name):
    client, _ = admin_client_mfp

    assert client.get(reverse(url_name)).status_code == 200


@pytest.mark.django_db
def test_la_page_de_modification_saffiche(admin_client_mfp):
    client, admin = admin_client_mfp

    response = client.get(reverse("admin:accounts_user_change", args=[admin.pk]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_le_hash_du_mot_de_passe_nest_jamais_rendu(admin_client_mfp):
    client, admin = admin_client_mfp

    response = client.get(reverse("admin:accounts_user_change", args=[admin.pk]))

    assert admin.password not in response.content.decode()


@pytest.mark.django_db
def test_creation_dun_utilisateur_depuis_ladmin(admin_client_mfp):
    client, _ = admin_client_mfp

    response = client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "Nouveau",
            "email": "",
            "first_name": "",
            "last_name": "",
            "status": UserStatus.PENDING,
            "usable_password": "true",
            "password1": "un-mot-de-passe-solide-1",
            "password2": "un-mot-de-passe-solide-1",
        },
    )

    assert response.status_code == 302
    created = User.objects.get(username="Nouveau")
    assert created.normalized_username == "nouveau"
    assert created.status == UserStatus.PENDING


@pytest.mark.django_db
def test_acceptation_dune_demande_depuis_ladmin(
    admin_client_mfp, django_capture_on_commit_callbacks
):
    from accounts.models import RegistrationRequest

    demande = RegistrationRequest(
        first_name="Téo", last_name="Maitrot", username="teo", email="teo@example.com"
    )
    demande.set_password("un-mot-de-passe-solide-1")
    demande.save()

    client, _ = admin_client_mfp
    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("admin:accounts_registrationrequest_changelist"),
            {"action": "accept_requests", "_selected_action": [str(demande.pk)]},
            follow=True,
        )

    created = User.objects.get(normalized_username="teo")
    assert created.status == UserStatus.ACTIVE
    assert created.check_password("un-mot-de-passe-solide-1")
    assert RegistrationRequest.objects.count() == 0


@pytest.mark.django_db
def test_refus_dune_demande_depuis_ladmin(admin_client_mfp, django_capture_on_commit_callbacks):
    from accounts.models import RegistrationRequest

    demande = RegistrationRequest(first_name="Téo", last_name="Maitrot", username="teo")
    demande.set_password("un-mot-de-passe-solide-1")
    demande.save()

    client, _ = admin_client_mfp
    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("admin:accounts_registrationrequest_changelist"),
            {"action": "reject_requests", "_selected_action": [str(demande.pk)]},
            follow=True,
        )

    assert RegistrationRequest.objects.count() == 0
    assert User.objects.filter(normalized_username="teo").exists() is False


@pytest.mark.django_db
def test_la_liste_des_demandes_saffiche(admin_client_mfp):
    client, _ = admin_client_mfp

    response = client.get(reverse("admin:accounts_registrationrequest_changelist"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_le_hash_dune_demande_nest_pas_affiche(admin_client_mfp):
    from accounts.models import RegistrationRequest

    demande = RegistrationRequest(first_name="Téo", last_name="Maitrot", username="teo")
    demande.set_password("un-mot-de-passe-solide-1")
    demande.save()

    client, _ = admin_client_mfp
    response = client.get(reverse("admin:accounts_registrationrequest_change", args=[demande.pk]))

    assert demande.password not in response.content.decode()


@pytest.mark.django_db
def test_la_suspension_revoque_les_sessions(admin_client_mfp):
    from django.conf import settings
    from rest_framework.test import APIClient

    from accounts.services.sessions import build_refresh_token

    client, _ = admin_client_mfp
    cible = User.objects.create_user(
        username="teo", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )

    session = APIClient()
    session.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(build_refresh_token(cible).access_token)
    assert session.get(reverse("api-v1:auth:me")).status_code == 200

    client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "suspend_accounts", "_selected_action": [str(cible.pk)]},
        follow=True,
    )

    cible.refresh_from_db()
    assert cible.status == UserStatus.SUSPENDED
    # La suspension coupe les sessions en cours, pas seulement les connexions
    # futures (spec 05 §2).
    assert session.get(reverse("api-v1:auth:me")).status_code == 401


@pytest.mark.django_db
def test_forcer_la_reinitialisation_envoie_un_lien(admin_client_mfp):
    from django.core import mail

    client, _ = admin_client_mfp
    cible = User.objects.create_user(
        username="teo",
        password="un-mot-de-passe-solide-1",
        status=UserStatus.ACTIVE,
        email="teo@example.com",
    )

    client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "force_password_reset", "_selected_action": [str(cible.pk)]},
        follow=True,
    )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["teo@example.com"]


@pytest.mark.django_db
def test_forcer_la_reinitialisation_sans_email_bloque_le_mot_de_passe(admin_client_mfp):
    client, _ = admin_client_mfp
    cible = User.objects.create_user(
        username="teo", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )

    client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "force_password_reset", "_selected_action": [str(cible.pk)]},
        follow=True,
    )

    cible.refresh_from_db()
    assert cible.has_usable_password() is False


@pytest.mark.django_db
def test_action_dactivation_des_comptes(admin_client_mfp):
    client, _ = admin_client_mfp
    pending = User.objects.create_user(username="teo", password="un-mot-de-passe-1")

    client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "activate_accounts", "_selected_action": [str(pending.pk)]},
        follow=True,
    )

    pending.refresh_from_db()
    assert pending.status == UserStatus.ACTIVE
