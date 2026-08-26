"""Unités de saisie d'un aliment et conversion en multiplicateur (spec 01 §9).

Ce module vit dans `nutrition` et non dans `diary` : les unités utilisables
sont une propriété de l'aliment, que le journal consomme sans la définir.

Les valeurs nutritionnelles d'un aliment portent sur une quantité de référence
— 100 g le plus souvent. Journaliser « 150 g » revient donc à appliquer un
multiplicateur de 1,5.

La règle qui gouverne ce module est celle de la spec 01 §9 : **jamais de
conversion millilitres ↔ grammes sans densité connue**. Les unités proposables
dépendent donc de l'unité de référence de l'aliment :

======  =========================================================
Réf.    Unités acceptées
======  =========================================================
g       g, kg, portions ayant un équivalent en grammes
ml      ml, cl, c. à café, c. à soupe, portions en millilitres
unit    unité, portions ayant un équivalent en unités
======  =========================================================

Les cuillères sont des mesures de volume : les proposer sur un aliment exprimé
en grammes reviendrait à inventer une densité. Beaucoup d'applications le font,
au prix de valeurs fausses sur tout ce qui n'a pas la densité de l'eau.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError

from nutrition.models import UnitType

TEASPOON = "cuillère à café"
TABLESPOON = "cuillère à soupe"


@dataclass(frozen=True)
class UnitDefinition:
    """Unité de saisie et sa valeur dans l'unité de référence."""

    label: str
    #: Unité de référence à laquelle cette unité s'applique.
    reference_unit: str
    #: Combien d'unités de référence vaut une unité saisie.
    factor: Decimal


#: Unités fixes, indépendantes de l'aliment.
BASE_UNITS: tuple[UnitDefinition, ...] = (
    UnitDefinition("g", UnitType.GRAM, Decimal("1")),
    UnitDefinition("kg", UnitType.GRAM, Decimal("1000")),
    UnitDefinition("ml", UnitType.MILLILITER, Decimal("1")),
    UnitDefinition("cl", UnitType.MILLILITER, Decimal("10")),
    # Mesures ménagères usuelles, volumétriques par nature.
    UnitDefinition(TEASPOON, UnitType.MILLILITER, Decimal("5")),
    UnitDefinition(TABLESPOON, UnitType.MILLILITER, Decimal("15")),
    UnitDefinition("unité", UnitType.UNIT, Decimal("1")),
)

#: Équivalent de portion à lire selon l'unité de référence de l'aliment.
PORTION_EQUIVALENT_FIELD = {
    UnitType.GRAM: "gram_equivalent",
    UnitType.MILLILITER: "milliliter_equivalent",
    UnitType.UNIT: "unit_equivalent",
}


def portion_factor(portion, reference_unit: str) -> Decimal | None:
    """Valeur d'une portion dans l'unité de référence, si elle est connue.

    Une portion exprimée en grammes ne dit rien d'un aliment mesuré en
    millilitres : elle est alors inutilisable, et non convertie au jugé.
    """
    field = PORTION_EQUIVALENT_FIELD.get(reference_unit)
    if field is None:
        return None
    return getattr(portion, field, None)


def available_units(food) -> list[str]:
    """Unités réellement utilisables pour cet aliment.

    L'API l'expose afin que l'interface ne propose jamais une unité que le
    backend refuserait.
    """
    reference_unit = food.reference_unit
    labels = [unit.label for unit in BASE_UNITS if unit.reference_unit == reference_unit]

    for portion in food.portions.all():
        if portion_factor(portion, reference_unit) is not None and portion.name not in labels:
            labels.append(portion.name)

    return labels


def resolve_factor(food, unit_label: str) -> Decimal:
    """Valeur d'une unité saisie, exprimée dans l'unité de référence.

    Lève `ValidationError` quand l'unité n'est pas calculable pour cet aliment,
    plutôt que de produire une approximation.
    """
    label = (unit_label or "").strip()
    reference_unit = food.reference_unit

    for unit in BASE_UNITS:
        if unit.label != label:
            continue
        if unit.reference_unit != reference_unit:
            raise ValidationError(
                {
                    "unit_label": (
                        f"L’unité « {label} » ne peut pas être convertie pour cet aliment, "
                        f"dont les valeurs portent sur des {reference_unit}. "
                        "Choisissez une autre unité ou ajoutez une portion."
                    )
                }
            )
        return unit.factor

    for portion in food.portions.all():
        if portion.name == label:
            factor = portion_factor(portion, reference_unit)
            if factor is None:
                raise ValidationError(
                    {
                        "unit_label": (
                            f"La portion « {label} » n’indique pas d’équivalent en "
                            f"{reference_unit} : elle est inutilisable pour cet aliment."
                        )
                    }
                )
            return Decimal(factor)

    raise ValidationError({"unit_label": f"L’unité « {label} » est inconnue pour cet aliment."})


def multiplier(reference_amount: Decimal, quantity: Decimal, factor: Decimal) -> Decimal:
    """Facteur à appliquer aux valeurs de référence."""
    return (Decimal(quantity) * Decimal(factor)) / Decimal(reference_amount)


def resolve_multiplier(food, quantity: Decimal, unit_label: str) -> Decimal:
    """Multiplicateur nutritionnel d'une quantité saisie sur un aliment."""
    return multiplier(food.reference_amount, quantity, resolve_factor(food, unit_label))
