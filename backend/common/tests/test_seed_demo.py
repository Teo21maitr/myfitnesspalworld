"""Comptes de démonstration (CLAUDE.md §4).

Ces tests protègent deux choses. D'abord que la commande **refuse** de
s'exécuter là où elle ferait des dégâts. Ensuite que les comptes qu'elle
fabrique ressemblent à des comptes que l'application aurait pu produire : un
jeu de démonstration incohérent masquerait les défauts au lieu de les révéler.
"""

from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command

from accounts.models import User
from diary.models import DiaryEntry
from nutrition.models import Food, FoodNutrition, FoodSource
from recipes.models import Recipe
from social.models import ResourceType
from social.services.sharing import can_read, opened_to

pytestmark = pytest.mark.django_db


@pytest.fixture
def reference(db):
    """Un référentiel minimal : la commande refuse de tourner sans."""
    for index, name in enumerate(
        ["Riz blanc cuit", "Poulet rôti", "Pomme", "Courgette", "Pain de mie", "Yaourt nature"]
    ):
        food = Food.objects.create(
            source=FoodSource.CIQUAL,
            external_id=f"seed-{index}",
            name=name,
            search_text=name.casefold(),
        )
        FoodNutrition.objects.create(
            food=food,
            energy_kcal=Decimal("150"),
            protein_g=Decimal("8"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("4"),
        )


#: Assez court pour que la suite reste rapide, assez long pour que les
#: journées vides et la moyenne mobile aient un sens.
DAYS = 21


def seed(**kwargs):
    call_command("seed_demo", days=DAYS, **kwargs)


class TestGuards:
    def test_sans_referentiel_la_commande_s_arrete(self, db):
        """Un compte de démonstration sans aliments ne démontrerait rien."""
        with pytest.raises(CommandError, match="import_ciqual"):
            seed()

    def test_elle_refuse_les_reglages_de_production(self, reference, settings):
        settings.SETTINGS_MODULE = "config.settings.production"

        with pytest.raises(CommandError, match="production"):
            seed()

    def test_elle_refuse_d_ecraser_sans_reset(self, reference):
        seed()

        with pytest.raises(CommandError, match="--reset"):
            seed()

    def test_reset_recree_les_comptes(self, reference):
        seed()
        premier = User.objects.get(username="demo").id

        seed(reset=True)

        assert User.objects.get(username="demo").id != premier
        assert User.objects.filter(username="demo").count() == 1


class TestTheAccountLooksReal:
    @pytest.fixture(autouse=True)
    def seeded(self, reference):
        seed(password="un-mot-de-passe-de-test-1")

    @pytest.fixture
    def demo(self):
        return User.objects.get(username="demo")

    def test_l_onboarding_est_termine(self, demo):
        assert demo.profile.onboarding_completed
        assert demo.nutrition_goals.exists()

    def test_les_entrees_portent_un_snapshot(self, demo):
        """Sans snapshot, le journal serait illisible dès la première suppression."""
        entries = DiaryEntry.objects.filter(diary_day__user=demo)

        assert entries.exists()
        assert not entries.filter(snapshot_name="").exists()
        assert not entries.filter(snapshot_energy_kcal__isnull=True).exists()

    def test_des_journees_restent_volontairement_vides(self, demo):
        """La règle des moyennes sur les journées tenues doit se voir."""
        from datetime import timedelta

        from django.utils import timezone

        from diary.services import analysis

        today = timezone.localdate()
        tenues = analysis.logged_days(demo, today - timedelta(days=DAYS - 1), today)

        assert 0 < len(tenues) < DAYS

    def test_les_recettes_ont_un_cache_calcule(self, demo):
        """Un cache posé à la main serait faux dès le premier ingrédient partiel."""
        recettes = Recipe.objects.filter(owner=demo)

        assert recettes.exists()
        for recipe in recettes:
            assert recipe.nutrition.energy_kcal is not None

    def test_le_compte_a_des_pesees_et_des_mensurations(self, demo):
        assert demo.weight_entries.count() == DAYS
        assert demo.body_measurements.count() == 8


class TestSocialFixture:
    @pytest.fixture(autouse=True)
    def seeded(self, reference):
        seed(password="un-mot-de-passe-de-test-1")

    def test_camille_a_ouvert_son_journal_et_sa_progression(self):
        demo = User.objects.get(username="demo")
        camille = User.objects.get(username="camille")

        assert can_read(demo, camille, ResourceType.DIARY)
        assert can_read(demo, camille, ResourceType.PROGRESS)

    def test_mathis_n_a_rien_ouvert(self):
        """C'est lui qui prouve qu'aucun bouton n'est proposé."""
        demo = User.objects.get(username="demo")
        mathis = User.objects.get(username="mathis")

        assert not can_read(demo, mathis, ResourceType.DIARY)
        assert not can_read(demo, mathis, ResourceType.PROGRESS)

    def test_les_drapeaux_distinguent_les_deux_amis(self):
        demo = User.objects.get(username="demo")
        camille = User.objects.get(username="camille")
        mathis = User.objects.get(username="mathis")

        opened = opened_to(demo)

        assert camille.id in opened[ResourceType.DIARY]
        assert mathis.id not in opened[ResourceType.DIARY]

    def test_une_demande_d_ami_attend(self):
        from social.models import FriendRequestStatus

        sofia = User.objects.get(username="sofia")

        assert sofia.sent_friend_requests.filter(status=FriendRequestStatus.PENDING).exists()


def test_deux_executions_donnent_le_meme_journal(reference):
    """Graine fixe : un défaut observé une fois doit se reproduire."""
    seed(password="un-mot-de-passe-de-test-1")
    premier = DiaryEntry.objects.filter(diary_day__user__username="demo").count()

    seed(reset=True, password="un-mot-de-passe-de-test-1")
    second = DiaryEntry.objects.filter(diary_day__user__username="demo").count()

    assert premier == second
