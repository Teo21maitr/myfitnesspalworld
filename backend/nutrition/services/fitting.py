"""Ajustement des quantités pour atteindre des objectifs (spec 01 §15).

Un modèle de langage choisit bien **quoi** manger et mal **combien**. Viser
simultanément des calories et trois macronutriments en dosant quinze aliments
est une optimisation sous contraintes ; la lui demander de tête produit des
journées à 20 % de la cible, et lui redemander de corriger ne fait que déplacer
l'erreur.

Ce module fait cette arithmétique-là, exactement et sans modèle : à composition
donnée, il cherche les quantités qui approchent au plus près les objectifs.

La répartition des rôles devient alors nette. Le modèle propose une
composition — des aliments, à des repas, dans des proportions plausibles. Le
backend la met à l'échelle. Et quand même l'ajustement ne suffit pas, c'est que
la **composition** est en cause, pas les quantités : c'est cela qu'on redemande
au modèle, et c'est une question à laquelle il sait répondre.
"""

from dataclasses import dataclass
from decimal import Decimal

#: Bornes du facteur appliqué à une quantité proposée.
#:
#: Sans elles, l'ajustement ferait disparaître un aliment ou en servirait cinq
#: fois trop : la composition proposée doit rester reconnaissable.
MIN_FACTOR = Decimal("0.4")
MAX_FACTOR = Decimal("2.5")

#: Passes d'ajustement. La descente par coordonnées converge vite ; au-delà, les
#: gains sont sous le bruit de l'arrondi.
PASSES = 6

#: Pas d'arrondi selon l'unité. Personne ne pèse 237 g de flocons d'avoine.
ROUNDING = {
    "g": Decimal("5"),
    "ml": Decimal("5"),
    "kg": Decimal("0.05"),
    "cl": Decimal("0.5"),
    "unité": Decimal("0.5"),
    "portion": Decimal("0.5"),
}
DEFAULT_ROUNDING = Decimal("0.5")

#: En deçà, l'arrondi au pas courant écraserait la quantité.
FINE_THRESHOLD = Decimal("20")
FINE_ROUNDING = Decimal("1")


@dataclass
class Adjustable:
    """Un élément dont la quantité peut être ajustée.

    `values` porte son apport **à la quantité actuelle** : c'est ce qui rend
    l'ajustement linéaire, donc soluble.
    """

    quantity: Decimal
    unit_label: str
    values: dict[str, Decimal | None]


def _step(unit_label: str, quantity: Decimal) -> Decimal:
    if quantity < FINE_THRESHOLD and unit_label in {"g", "ml"}:
        return FINE_ROUNDING
    return ROUNDING.get(unit_label, DEFAULT_ROUNDING)


def _round(quantity: Decimal, unit_label: str) -> Decimal:
    """Arrondit à un pas qu'un humain saurait servir."""
    step = _step(unit_label, quantity)
    rounded = (quantity / step).quantize(Decimal("1")) * step
    return max(rounded, step)


def _weights(tolerances: dict[str, Decimal]) -> dict[str, Decimal]:
    """Une cible deux fois plus serrée pèse quatre fois plus.

    Les calories tolèrent ±5 % et les macros ±10 % : l'écart sur les calories
    doit donc peser davantage dans ce qu'on cherche à minimiser.
    """
    return {name: 1 / (value * value) for name, value in tolerances.items()}


def fit(
    items: list[Adjustable],
    *,
    targets: dict[str, Decimal],
    nutrients: dict[str, str],
    tolerances: dict[str, Decimal],
) -> list[Decimal]:
    """Renvoie les quantités ajustées, dans l'ordre reçu.

    `targets` porte les objectifs, `nutrients` dit quel nutriment correspond à
    chacun. Un objectif absent ou nul est ignoré : il n'y a rien à viser.

    Une valeur nutritionnelle inconnue compte pour zéro **dans l'ajustement
    seulement** : on ne peut pas optimiser contre ce qu'on ne sait pas. Les
    totaux affichés, eux, gardent la distinction entre inconnu et nul
    (spec 01 §8).
    """
    aimed = {
        name: Decimal(targets[name])
        for name in nutrients
        if targets.get(name) is not None and Decimal(targets[name]) != 0
    }
    if not items or not aimed:
        return [item.quantity for item in items]

    weights = _weights(tolerances)

    def value_of(item: Adjustable, name: str) -> Decimal:
        raw = item.values.get(nutrients[name])
        return Decimal(0) if raw is None else Decimal(raw)

    factors = [Decimal(1)] * len(items)

    for _ in range(PASSES):
        for index, item in enumerate(items):
            numerator = Decimal(0)
            denominator = Decimal(0)

            for name, target in aimed.items():
                own = value_of(item, name)
                if own == 0:
                    continue

                # Ce que les autres apportent déjà, à leurs facteurs courants.
                others = sum(
                    factors[other] * value_of(items[other], name)
                    for other in range(len(items))
                    if other != index
                )
                weight = weights[name]
                numerator += weight * own * (target - others) / (target * target)
                denominator += weight * own * own / (target * target)

            if denominator == 0:
                continue

            factors[index] = min(max(numerator / denominator, MIN_FACTOR), MAX_FACTOR)

    return [
        _round(item.quantity * factor, item.unit_label)
        for item, factor in zip(items, factors, strict=True)
    ]
