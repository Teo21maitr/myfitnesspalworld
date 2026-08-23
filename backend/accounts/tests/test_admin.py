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
