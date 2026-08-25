"""Client HTTP d'Open Food Facts (spec 11 §3).

Ce module est la seule frontière réseau de la source : il renvoie des données
déjà validées et ne laisse jamais remonter une exception `requests` ni une
charge utile brute vers les vues.

Deux services distincts sont interrogés :

* la lecture d'un produit par `GET /api/v3/product/{code}.json` ;
* la recherche texte par Search-a-licious, l'endpoint historique
  `/api/v2/search` renvoyant une page d'erreur HTML.

Le mode de panne réel de cette API est d'ailleurs de répondre **HTML au lieu de
JSON** ; c'est le premier cas traité ici.

Attribution à conserver : les données proviennent d'Open Food Facts, sous
licence ODbL.
"""

import logging
from dataclasses import dataclass

import requests
from django.conf import settings

from common.rate_limit import consume_budget

logger = logging.getLogger(__name__)

#: Champs demandés à l'API. Les restreindre allège la réponse et documente
#: exactement ce dont la conversion a besoin.
PRODUCT_FIELDS = (
    "code",
    "product_name",
    "product_name_fr",
    "generic_name_fr",
    "brands",
    "quantity",
    "serving_size",
    "nutrition_data_per",
    "nutriments",
    "last_modified_t",
    "lang",
)

SEARCH_FIELDS = ("code", "product_name", "brands")

#: Noms des budgets globaux, partagés par tous les comptes.
PRODUCT_BUDGET = "off:product"
SEARCH_BUDGET = "off:search"


class OpenFoodFactsError(Exception):
    """Base des erreurs de la source."""


class OpenFoodFactsUnavailable(OpenFoodFactsError):
    """La source n'a pas pu être interrogée, ou a répondu autre chose que du JSON.

    Couvre indifféremment la panne réseau, le délai dépassé, le 429, le 503 et
    la page HTML d'erreur : côté appelant il n'y a qu'une conduite à tenir,
    servir les données locales et le dire.
    """


class ProductNotFound(OpenFoodFactsError):
    """Le code-barres est inconnu d'Open Food Facts.

    Ce n'est pas une panne : c'est le cas nominal qui mène à la création
    manuelle d'un produit (spec 01 §10).
    """


@dataclass(frozen=True)
class ProductCandidate:
    """Résultat de recherche : de quoi choisir, pas de quoi manger.

    La recherche ne sert qu'à découvrir un code-barres. Les valeurs
    nutritionnelles viennent toujours ensuite de l'endpoint produit, qui fait
    seul autorité — sans quoi il faudrait écrire et maintenir deux conversions
    pour deux formes de charge utile différentes.
    """

    code: str
    name: str
    brand: str


def _headers() -> dict[str, str]:
    # Open Food Facts demande un User-Agent identifiant l'application et un
    # contact, faute de quoi l'appel peut être pris pour celui d'un robot.
    return {"User-Agent": settings.OFF_USER_AGENT, "Accept": "application/json"}


def _timeout() -> tuple[float, float]:
    return (settings.OFF_CONNECT_TIMEOUT, settings.OFF_READ_TIMEOUT)


def _get_json(url: str, params: dict, budget: str, limit: int) -> tuple[dict, int]:
    """Exécute l'appel et renvoie `(charge utile, statut)`.

    Lève `OpenFoodFactsUnavailable` pour tout ce qui n'est pas une réponse JSON
    exploitable, statut d'erreur compris — sauf le 404, que l'appelant doit
    pouvoir distinguer.
    """
    if not settings.OFF_ENABLED:
        raise OpenFoodFactsUnavailable("La source Open Food Facts est désactivée.")

    # Le budget est vérifié avant l'appel : quand il est épuisé, aucune requête
    # ne part. C'est tout l'intérêt d'un compteur local.
    if not consume_budget(budget, limit):
        raise OpenFoodFactsUnavailable("Le quota d’appels à Open Food Facts est atteint.")

    try:
        response = requests.get(url, params=params, headers=_headers(), timeout=_timeout())
    except requests.RequestException as error:
        # Le message de `requests` peut contenir l'URL complète : on ne
        # journalise que le type d'erreur (spec 05 §15).
        logger.warning("Open Food Facts injoignable : %s", type(error).__name__)
        raise OpenFoodFactsUnavailable("Open Food Facts est injoignable.") from error

    if response.status_code >= 500 or response.status_code == 429:
        logger.warning("Open Food Facts a répondu %s", response.status_code)
        raise OpenFoodFactsUnavailable("Open Food Facts est momentanément indisponible.")

    try:
        payload = response.json()
    except ValueError as error:
        # Cas réellement observé : une page HTML « Page temporarily
        # unavailable » servie avec un statut 200.
        logger.warning("Open Food Facts a répondu autre chose que du JSON.")
        raise OpenFoodFactsUnavailable("Open Food Facts est momentanément indisponible.") from error

    if not isinstance(payload, dict):
        raise OpenFoodFactsUnavailable("Réponse inattendue d’Open Food Facts.")

    return payload, response.status_code


def fetch_product(barcode: str) -> dict:
    """Renvoie la fiche brute d'un produit, ou lève `ProductNotFound`."""
    url = f"{settings.OFF_PRODUCT_URL}/api/v3/product/{barcode}.json"
    params = {"fields": ",".join(PRODUCT_FIELDS), "lc": "fr", "cc": "fr"}

    payload, status_code = _get_json(
        url, params, PRODUCT_BUDGET, settings.OFF_PRODUCT_RATE_PER_MINUTE
    )

    product = payload.get("product")
    if status_code == 404 or not product:
        raise ProductNotFound(barcode)

    return product


def search_products(query: str, limit: int = 25) -> list[ProductCandidate]:
    """Cherche des produits par texte. Renvoie une liste éventuellement vide."""
    url = f"{settings.OFF_SEARCH_URL}/search"
    params = {
        "q": query,
        "page_size": limit,
        "fields": ",".join(SEARCH_FIELDS),
        "langs": "fr",
    }

    payload, _ = _get_json(url, params, SEARCH_BUDGET, settings.OFF_SEARCH_RATE_PER_MINUTE)

    hits = payload.get("hits")
    if not isinstance(hits, list):
        raise OpenFoodFactsUnavailable("Réponse de recherche inattendue d’Open Food Facts.")

    return [candidate for hit in hits if (candidate := _read_candidate(hit)) is not None]


def _read_candidate(hit: object) -> ProductCandidate | None:
    """Convertit un résultat de recherche, ou l'écarte s'il est inexploitable."""
    if not isinstance(hit, dict):
        return None

    code = hit.get("code")
    name = hit.get("product_name")
    if not code or not name:
        # Sans code-barres ni nom, le résultat ne mène à rien.
        return None

    # `brands` est un tableau ici, alors que l'endpoint produit renvoie une
    # chaîne « Nutella, Ferrero ». Les deux formes se ramènent à la première
    # marque, la plus significative.
    brands = hit.get("brands")
    if isinstance(brands, list):
        brand = str(brands[0]) if brands else ""
    else:
        brand = str(brands or "").split(",")[0]

    return ProductCandidate(code=str(code), name=str(name).strip(), brand=brand.strip())
