"""Import de la table Ciqual (spec 11 §2).

L'analyse des teneurs est ce qui décide de la qualité de toute la base : une
donnée non mesurée doit rester inconnue, pas devenir un zéro (spec 01 §8).
"""

from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command

from nutrition.models import Food, FoodNutrition, FoodSource
from nutrition.services.ciqual import (
    BETA_CAROTENE_TO_RETINOL,
    CiqualFood,
    parse_teneur,
    read_foods,
    sanitize_xml_line,
)

# --- Analyse des teneurs ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("59,7", Decimal("59.7")),
        ("0,002", Decimal("0.002")),
        ("1140", Decimal("1140")),
        (" 274 ", Decimal("274")),
    ],
)
def test_une_teneur_numerique_est_convertie(raw, expected):
    """La table utilise la virgule décimale française."""
    assert parse_teneur(raw) == expected


@pytest.mark.parametrize("raw", ["-", "", "   ", None])
def test_une_teneur_non_mesuree_reste_inconnue(raw):
    """Un tiret signifie « non mesuré » : jamais zéro (spec 01 §8)."""
    assert parse_teneur(raw) is None


@pytest.mark.parametrize("raw", ["traces", "Traces", "< 0,01", "<0,1", "< 20"])
def test_une_teneur_negligeable_vaut_zero(raw):
    """Mesurée mais sous le seuil de détection : c'est un zéro, pas un inconnu."""
    assert parse_teneur(raw) == Decimal("0")


def test_une_teneur_incomprehensible_est_traitee_comme_inconnue():
    assert parse_teneur("environ 12") is None


# --- Assainissement du XML ----------------------------------------------------


def test_les_chevrons_bruts_sont_echappes():
    """Les fichiers de l'Anses ne sont pas du XML bien formé."""
    line = b"<teneur> < 0,01 </teneur>"

    assert sanitize_xml_line(line) == b"<teneur> &lt; 0,01 </teneur>"


def test_un_nom_contenant_un_chevron_est_echappe():
    line = b"<alim_nom_fr> Panache preemballe (<1 alc.) </alim_nom_fr>"

    assert b"&lt;1 alc." in sanitize_xml_line(line)


def test_les_balises_ne_sont_pas_touchees():
    line = b"   <ALIM>\r\n"

    assert sanitize_xml_line(line) == line


def test_une_esperluette_isolee_est_echappee():
    assert sanitize_xml_line(b"<n> sel & poivre </n>") == b"<n> sel &amp; poivre </n>"


def test_une_entite_valide_est_preservee():
    assert sanitize_xml_line(b"<n> a &amp; b </n>") == b"<n> a &amp; b </n>"


# --- Vitamine A ---------------------------------------------------------------


def test_la_vitamine_a_combine_retinol_et_beta_carotene():
    """Ciqual ne publie pas de vitamine A : elle se reconstitue."""
    food = CiqualFood(
        code="1", name="Test", retinol_ug=Decimal("100"), beta_carotene_ug=Decimal("600")
    )

    assert food.vitamin_a_ug() == Decimal("100") + Decimal("600") / BETA_CAROTENE_TO_RETINOL


def test_la_vitamine_a_reste_inconnue_sans_aucune_source():
    food = CiqualFood(code="1", name="Test")

    assert food.vitamin_a_ug() is None


def test_la_vitamine_a_tolere_une_source_absente():
    food = CiqualFood(code="1", name="Test", retinol_ug=Decimal("42"))

    assert food.vitamin_a_ug() == Decimal("42")


# --- Import complet sur des données réelles -----------------------------------

CIQUAL_SAMPLE = Path(__file__).parent / "fixtures" / "ciqual"

pytestmark_dataset = pytest.mark.skipif(not CIQUAL_SAMPLE.exists(), reason="extrait Ciqual absent")


@pytest.fixture
def ciqual_sample():
    if not CIQUAL_SAMPLE.exists():
        pytest.skip("extrait Ciqual absent")
    return CIQUAL_SAMPLE


def test_lecture_de_lextrait(ciqual_sample):
    foods = read_foods(ciqual_sample)

    assert foods
    first = next(iter(foods.values()))
    assert first.name


@pytest.mark.django_db
def test_import_cree_les_aliments(ciqual_sample):
    call_command("import_ciqual", str(ciqual_sample))

    assert Food.objects.filter(source=FoodSource.CIQUAL).exists()
    assert FoodNutrition.objects.exists()


@pytest.mark.django_db
def test_import_est_idempotent(ciqual_sample):
    """Relancer l'import met à jour au lieu de dupliquer."""
    call_command("import_ciqual", str(ciqual_sample))
    first_count = Food.objects.count()

    call_command("import_ciqual", str(ciqual_sample))

    assert Food.objects.count() == first_count


@pytest.mark.django_db
def test_les_accents_sont_correctement_decodes(ciqual_sample):
    """Le fichier est encodé en windows-1252, pas en UTF-8."""
    call_command("import_ciqual", str(ciqual_sample))

    assert Food.objects.filter(name__contains="é").exists()


@pytest.mark.django_db
def test_les_fiches_ciqual_sont_verifiees_et_globales(ciqual_sample):
    call_command("import_ciqual", str(ciqual_sample))

    food = Food.objects.filter(source=FoodSource.CIQUAL).first()
    assert food.is_verified is True
    assert food.owner is None
    assert food.reference_amount == Decimal("100.00")


@pytest.mark.django_db
def test_les_valeurs_inconnues_restent_nulles(ciqual_sample):
    """Aucune teneur absente ne doit avoir été convertie en zéro."""
    call_command("import_ciqual", str(ciqual_sample))

    assert FoodNutrition.objects.filter(vitamin_k_ug__isnull=True).exists()


@pytest.mark.django_db
def test_import_sur_un_chemin_inexistant():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="introuvable"):
        call_command("import_ciqual", "/chemin/qui/nexiste/pas")
