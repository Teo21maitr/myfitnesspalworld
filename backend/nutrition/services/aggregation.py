"""Totalisation de valeurs nutritionnelles (spec 01 §8).

La règle est la même partout : une valeur inconnue n'est pas zéro. L'ignorer
dans une somme reviendrait à la compter pour zéro, ce qui produirait un total
faux présenté comme exact.

Le total reste donc utile — il additionne ce qu'on sait — mais les nutriments
dont au moins une source manquait sont signalés, à charge pour l'interface de
présenter le résultat comme partiel.

Ce module est partagé par le journal et les recettes : écrire cette règle deux
fois la ferait diverger.
"""

from collections.abc import Iterable, Sequence
from decimal import Decimal


def sum_values(
    rows: Iterable[dict[str, Decimal | None]], names: Sequence[str]
) -> tuple[dict[str, Decimal | None], list[str]]:
    """Somme plusieurs jeux de nutriments.

    Renvoie les totaux et la liste triée des nutriments partiels — connus d'au
    moins une source, inconnus d'au moins une autre.

    Sans aucune source, les totaux valent zéro et non « inconnu » : on sait que
    rien n'a été consommé. Un nutriment qu'aucune source ne renseigne reste
    `None` : là, on ne sait pas.
    """
    materialized = list(rows)
    if not materialized:
        return dict.fromkeys(names, Decimal(0)), []

    # Toujours la même forme : l'appelant n'a pas à distinguer « nutriment
    # absent de la réponse » de « inconnu ».
    totals: dict[str, Decimal | None] = dict.fromkeys(names)
    known: dict[str, bool] = {}
    incomplete: set[str] = set()

    for row in materialized:
        for name in names:
            value = row.get(name)
            if value is None:
                incomplete.add(name)
                continue

            totals[name] = value if not known.get(name) else totals[name] + value
            known[name] = True

    for name in names:
        if not known.get(name):
            totals[name] = None

    return totals, sorted(incomplete & set(known))
