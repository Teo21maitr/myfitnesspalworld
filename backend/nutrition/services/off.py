"""Conversion d'un produit Open Food Facts en fiche locale (spec 11 §3).

Trois pièges rendent cette conversion moins évidente qu'elle n'en a l'air. Ils
ont été vérifiés sur des produits réels, et chacun a son test :

1. **L'énergie.** `energy_100g` est exprimé en kilojoules, `energy-kcal_100g` en
   kilocalories. Pour le Nutella, 2252 contre 539 : confondre les deux multiplie
   les calories par 4,18.
2. **Les micronutriments sont en grammes.** Relevé sur produit réel :
   `calcium_100g = 0.148` avec `calcium_unit = "g"`. Le modèle stocke des
   milligrammes et des microgrammes.
3. **`nutrition_data_per`** peut valoir `serving`. Seules les clés `_100g` sont
   lues ; en leur absence la valeur reste inconnue plutôt que reconstituée.

Comme partout ailleurs, une donnée absente reste `NULL` et n'est jamais ramenée
à zéro (spec 01 §8).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from nutrition.models import Food, FoodNutrition, FoodSource, UnitType

logger = logging.getLogger(__name__)

#: Attribution à conserver dans l'application et la documentation.
OFF_ATTRIBUTION = "Open Food Facts, sous licence ODbL"

#: Champs nutritionnels du modèle, dans l'ordre de sa définition.
NUTRITION_FIELDS = [
    field.name for field in FoodNutrition._meta.fields if field.name not in {"id", "food"}
]

_ONE = Decimal("1")
_MILLI = Decimal("1000")
_MICRO = Decimal("1000000")

#: Plafonds de vraisemblance, exprimés dans l'unité du modèle et pour 100 g.
#:
#: Ils servent deux buts. D'abord écarter les valeurs aberrantes : la base est
#: collaborative et en contient. Ensuite, et surtout, protéger l'écriture —
#: les champs sont en `max_digits=9, decimal_places=3`, donc plafonnés à
#: 999 999,999. Sans borne, une saisie fantaisiste ferait échouer la requête
#: d'un utilisateur au niveau de la base de données.
_MAX_KCAL = Decimal("1000")  # 900 kcal/100 g pour un corps gras pur
_MAX_GRAM = Decimal("100")  # au-delà de 100 g pour 100 g, la valeur est fausse
_MAX_MILLIGRAM = Decimal("100000")  # 100 g exprimés en milligrammes
_MAX_MICROGRAM = Decimal("100000")  # très au-dessus des teneurs réelles


@dataclass(frozen=True)
class NutrientMapping:
    """Correspondance entre une clé Open Food Facts et un champ du modèle."""

    off_key: str
    factor: Decimal
    maximum: Decimal


#: Toutes les valeurs `_100g` d'Open Food Facts sont en grammes, à la seule
#: exception de l'énergie.
NUTRIENT_MAP: dict[str, NutrientMapping] = {
    "energy_kcal": NutrientMapping("energy-kcal_100g", _ONE, _MAX_KCAL),
    "protein_g": NutrientMapping("proteins_100g", _ONE, _MAX_GRAM),
    "carbohydrates_g": NutrientMapping("carbohydrates_100g", _ONE, _MAX_GRAM),
    "fat_g": NutrientMapping("fat_100g", _ONE, _MAX_GRAM),
    "fiber_g": NutrientMapping("fiber_100g", _ONE, _MAX_GRAM),
    "sugars_g": NutrientMapping("sugars_100g", _ONE, _MAX_GRAM),
    "salt_g": NutrientMapping("salt_100g", _ONE, _MAX_GRAM),
    "sodium_mg": NutrientMapping("sodium_100g", _MILLI, _MAX_MILLIGRAM),
    "cholesterol_mg": NutrientMapping("cholesterol_100g", _MILLI, _MAX_MILLIGRAM),
    "potassium_mg": NutrientMapping("potassium_100g", _MILLI, _MAX_MILLIGRAM),
    "calcium_mg": NutrientMapping("calcium_100g", _MILLI, _MAX_MILLIGRAM),
    "iron_mg": NutrientMapping("iron_100g", _MILLI, _MAX_MILLIGRAM),
    "magnesium_mg": NutrientMapping("magnesium_100g", _MILLI, _MAX_MILLIGRAM),
    "vitamin_b6_mg": NutrientMapping("vitamin-b6_100g", _MILLI, _MAX_MILLIGRAM),
    "vitamin_c_mg": NutrientMapping("vitamin-c_100g", _MILLI, _MAX_MILLIGRAM),
    "vitamin_e_mg": NutrientMapping("vitamin-e_100g", _MILLI, _MAX_MILLIGRAM),
    "vitamin_a_ug": NutrientMapping("vitamin-a_100g", _MICRO, _MAX_MICROGRAM),
    "vitamin_b12_ug": NutrientMapping("vitamin-b12_100g", _MICRO, _MAX_MICROGRAM),
    "vitamin_d_ug": NutrientMapping("vitamin-d_100g", _MICRO, _MAX_MICROGRAM),
    "vitamin_k_ug": NutrientMapping("vitamin-k_100g", _MICRO, _MAX_MICROGRAM),
}

#: Précision de stockage du modèle.
_QUANTUM = Decimal("0.001")


class UnusableProduct(Exception):
    """Le produit existe chez Open Food Facts mais ne porte pas de nom.

    Sans nom, la fiche ne peut ni s'afficher ni se rechercher : l'utilisateur
    est renvoyé vers la création manuelle, comme pour un code inconnu.
    """


def read_nutrient(nutriments: dict, mapping: NutrientMapping) -> Decimal | None:
    """Lit un nutriment et le convertit dans l'unité du modèle.

    Renvoie `None` — donc « inconnu » — quand la clé est absente, illisible,
    négative ou invraisemblable.
    """
    raw = nutriments.get(mapping.off_key)
    if raw is None or isinstance(raw, bool):
        return None

    try:
        # Le passage par `str` évite d'hériter du bruit binaire des flottants
        # renvoyés par l'API (0.148076923076923).
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if not value.is_finite() or value < 0:
        return None

    converted = value * mapping.factor
    if converted > mapping.maximum:
        # Valeur aberrante : la laisser inconnue est plus honnête que de la
        # tronquer, et évite un dépassement à l'écriture.
        return None

    return converted.quantize(_QUANTUM)


def read_nutrition(product: dict) -> dict[str, Decimal | None]:
    """Extrait tous les nutriments connus du produit."""
    nutriments = product.get("nutriments")
    if not isinstance(nutriments, dict):
        # Produit sans aucune donnée nutritionnelle : il reste utilisable, ses
        # valeurs sont simplement toutes inconnues (spec 01 §8).
        nutriments = {}

    values = dict.fromkeys(NUTRITION_FIELDS)
    for name, mapping in NUTRIENT_MAP.items():
        values[name] = read_nutrient(nutriments, mapping)
    return values


def read_name(product: dict) -> str:
    """Nom affiché, en préférant le français : l'application est francophone."""
    for key in ("product_name_fr", "product_name", "generic_name_fr"):
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
    return ""


def read_brand(product: dict) -> str:
    """Première marque de la liste, la plus significative."""
    brands = product.get("brands")
    if not isinstance(brands, str):
        return ""
    return brands.split(",")[0].strip()[:255]


def read_external_updated_at(product: dict) -> datetime | None:
    """Date de dernière modification chez Open Food Facts."""
    raw = product.get("last_modified_t")
    if not isinstance(raw, int) or isinstance(raw, bool) or raw <= 0:
        return None
    try:
        return datetime.fromtimestamp(raw, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def upsert_product(product: dict) -> Food:
    """Crée ou met à jour la fiche locale correspondant à un produit.

    L'idempotence repose sur la contrainte d'unicité `(source, external_id)`
    déjà posée sur `Food` : réimporter un produit le met à jour sans le
    dupliquer.
    """
    code = str(product.get("code") or "").strip()
    if not code:
        raise UnusableProduct("Produit sans code-barres.")

    name = read_name(product)
    if not name:
        raise UnusableProduct(code)

    food, _ = Food.objects.update_or_create(
        source=FoodSource.OFF,
        external_id=code,
        defaults={
            "name": name,
            "brand": read_brand(product),
            "barcode": code,
            # Base collaborative : une fiche n'est jamais présentée comme
            # vérifiée (spec 11 §3).
            "is_verified": False,
            "is_active": True,
            "deleted_at": None,
            "default_unit_type": UnitType.GRAM,
            # Open Food Facts normalise ses valeurs pour 100 g. Aucune
            # conversion ml ↔ g n'est tentée sans densité connue (spec 01 §9).
            "reference_unit": UnitType.GRAM,
            "reference_amount": 100,
            "external_updated_at": read_external_updated_at(product),
            "cache_refreshed_at": timezone.now(),
        },
    )

    FoodNutrition.objects.update_or_create(food=food, defaults=read_nutrition(product))

    return food
