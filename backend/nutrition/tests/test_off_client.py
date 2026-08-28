"""Client HTTP d'Open Food Facts (spec 11 §3).

Aucun test ne touche le réseau réel : les réponses sont simulées, y compris les
pannes. La source doit pouvoir tomber sans que l'application tombe avec elle.
"""

import json
from pathlib import Path

import pytest
import requests
import responses
from django.conf import settings

from common.rate_limit import consume_budget
from nutrition.services.off_client import (
    PRODUCT_BUDGET,
    OpenFoodFactsUnavailable,
    ProductNotFound,
    fetch_product,
    search_products,
)

FIXTURES = Path(__file__).parent / "fixtures" / "off"

PRODUCT_URL = f"{settings.OFF_PRODUCT_URL}/api/v3/product/3017620422003.json"
MISSING_URL = f"{settings.OFF_PRODUCT_URL}/api/v3/product/0000000000000.json"
SEARCH_URL = f"{settings.OFF_SEARCH_URL}/search"

#: Page d'erreur réellement servie par Open Food Facts en cas de saturation.
HTML_ERROR_PAGE = (
    "<!DOCTYPE html><html><head><title>Page temporarily unavailable</title></head></html>"
)


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --- Cas nominal -------------------------------------------------------------


@responses.activate
def test_un_produit_connu_est_renvoye():
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)

    product = fetch_product("3017620422003")

    assert product["code"] == "3017620422003"


@responses.activate
def test_l_appel_porte_un_user_agent_identifiant():
    """Open Food Facts l'exige, sous peine d'être pris pour un robot."""
    responses.add(responses.GET, PRODUCT_URL, json=fixture("product_nutella.json"), status=200)

    fetch_product("3017620422003")

    user_agent = responses.calls[0].request.headers["User-Agent"]
    assert "MyFitnessPalworld" in user_agent


# --- Produit inconnu contre panne --------------------------------------------


@responses.activate
def test_un_produit_inconnu_se_distingue_d_une_panne():
    """Le 404 est un cas nominal : il mène à la création manuelle (spec 01 §10)."""
    responses.add(responses.GET, MISSING_URL, json=fixture("product_not_found.json"), status=404)

    with pytest.raises(ProductNotFound):
        fetch_product("0000000000000")


# --- Modes de panne ----------------------------------------------------------


@responses.activate
def test_une_reponse_html_est_traitee_comme_une_panne():
    """Cas réellement observé : une page HTML servie avec un statut 200.

    Un `response.json()` naïf lèverait une exception non gérée en pleine
    requête utilisateur.
    """
    responses.add(
        responses.GET, PRODUCT_URL, body=HTML_ERROR_PAGE, status=200, content_type="text/html"
    )

    with pytest.raises(OpenFoodFactsUnavailable):
        fetch_product("3017620422003")


@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
@responses.activate
def test_les_statuts_d_erreur_sont_traites_comme_une_panne(status_code):
    responses.add(responses.GET, PRODUCT_URL, json={}, status=status_code)

    with pytest.raises(OpenFoodFactsUnavailable):
        fetch_product("3017620422003")


@pytest.mark.parametrize(
    "error",
    [requests.ConnectionError("injoignable"), requests.Timeout("trop long")],
    ids=["connexion", "delai"],
)
@responses.activate
def test_une_panne_reseau_est_absorbee(error):
    responses.add(responses.GET, PRODUCT_URL, body=error)

    with pytest.raises(OpenFoodFactsUnavailable):
        fetch_product("3017620422003")


@responses.activate
def test_une_charge_utile_sans_produit_est_traitee_comme_introuvable():
    responses.add(responses.GET, PRODUCT_URL, json={"status": "success"}, status=200)

    with pytest.raises(ProductNotFound):
        fetch_product("3017620422003")


# --- Coupe-circuit et budget -------------------------------------------------


@responses.activate
def test_la_source_desactivee_ne_declenche_aucun_appel(settings):
    settings.OFF_ENABLED = False

    with pytest.raises(OpenFoodFactsUnavailable):
        fetch_product("3017620422003")

    assert len(responses.calls) == 0


@responses.activate
def test_le_budget_epuise_ne_declenche_aucun_appel(settings):
    """Le budget global est vérifié avant l'appel, pas après.

    Open Food Facts limite par adresse IP : une fois le quota atteint,
    insister ne ferait qu'aggraver la situation.
    """
    settings.OFF_PRODUCT_RATE_PER_MINUTE = 2
    for _ in range(2):
        consume_budget(PRODUCT_BUDGET, 2)

    with pytest.raises(OpenFoodFactsUnavailable):
        fetch_product("3017620422003")

    assert len(responses.calls) == 0


# --- Recherche ---------------------------------------------------------------


@responses.activate
def test_la_recherche_renvoie_des_candidats():
    responses.add(responses.GET, SEARCH_URL, json=fixture("search_nutella.json"), status=200)

    candidates = search_products("nutella")

    assert len(candidates) == 3
    assert candidates[0].code == "0009800800049"
    # `brands` est un tableau côté recherche, une chaîne côté produit.
    assert candidates[0].brand == "Nutella"


@responses.activate
def test_les_resultats_inexploitables_sont_ecartes():
    """Sans code-barres ni nom, un résultat ne mène à rien."""
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={
            "hits": [
                {"code": "1", "product_name": "Bon", "brands": ["Marque"]},
                {"code": "2"},
                {"product_name": "Sans code"},
                "pas un objet",
            ]
        },
        status=200,
    )

    candidates = search_products("essai")

    assert [candidate.code for candidate in candidates] == ["1"]


@responses.activate
def test_une_recherche_sans_resultat_renvoie_une_liste_vide():
    responses.add(responses.GET, SEARCH_URL, json={"hits": []}, status=200)

    assert search_products("zzzzz") == []


@responses.activate
def test_une_reponse_de_recherche_malformee_est_traitee_comme_une_panne():
    responses.add(responses.GET, SEARCH_URL, json={"resultats": []}, status=200)

    with pytest.raises(OpenFoodFactsUnavailable):
        search_products("nutella")


class TestSearchLanguages:
    """Les langues interrogées décident de ce que la recherche voit.

    Coder le français en dur rendait invisibles les produits nommés dans une
    autre langue, alors même que le scan de code-barres, lui, n'a jamais eu
    cette restriction.
    """

    @responses.activate
    def test_les_langues_par_defaut_sont_transmises(self):
        responses.add(responses.GET, SEARCH_URL, json={"hits": []}, status=200)

        search_products("filmjölk")

        assert responses.calls[0].request.params["langs"] == "fr,en"

    @responses.activate
    def test_les_langues_demandees_sont_transmises(self):
        responses.add(responses.GET, SEARCH_URL, json={"hits": []}, status=200)

        search_products("filmjölk", languages=["fr", "sv", "en"])

        assert responses.calls[0].request.params["langs"] == "fr,sv,en"

    @responses.activate
    def test_une_liste_vide_retombe_sur_le_defaut(self):
        responses.add(responses.GET, SEARCH_URL, json={"hits": []}, status=200)

        search_products("filmjölk", languages=[])

        assert responses.calls[0].request.params["langs"] == "fr,en"
