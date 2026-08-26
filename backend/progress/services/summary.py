"""Résumé du poids pour le tableau de bord (spec 01 §19, spec 06 §5).

L'écran attend « 78,2 kg · -2,4 kg depuis le début » : le poids courant, le
chemin parcouru et, quand un poids cible existe, la part du trajet accomplie.
"""

from decimal import Decimal

from accounts.models import User
from progress.models import WeightEntry


def weight_summary(user: User) -> dict:
    """Poids courant, écart depuis la première pesée et progression.

    Chaque champ vaut `None` tant que la donnée manque : compte neuf, aucune
    pesée, ou aucun poids cible défini. C'est le cas normal au démarrage, pas
    une anomalie.
    """
    entries = WeightEntry.objects.filter(user=user).order_by("date")
    first = entries.first()
    latest = entries.last()

    profile = getattr(user, "profile", None)
    target = getattr(profile, "target_weight_kg", None)

    if latest is None:
        return {
            "latest_kg": None,
            "latest_date": None,
            "start_kg": None,
            "change_kg": None,
            "target_kg": target,
            "progress_percent": None,
        }

    start = first.weight_kg
    change = latest.weight_kg - start

    return {
        "latest_kg": latest.weight_kg,
        "latest_date": latest.date,
        "start_kg": start,
        "change_kg": change,
        "target_kg": target,
        "progress_percent": _progress_percent(start, latest.weight_kg, target),
    }


def _progress_percent(start: Decimal, current: Decimal, target: Decimal | None) -> Decimal | None:
    """Part du chemin parcouru entre le poids de départ et la cible.

    `None` quand il n'y a pas de cible, ou quand le départ vaut déjà la cible :
    il n'y aurait alors aucun trajet à mesurer.
    """
    if target is None:
        return None

    total = target - start
    if total == 0:
        return None

    ratio = (current - start) / total * 100
    # Le trajet peut être dépassé ou pris à l'envers ; l'affichage se contente
    # de la part accomplie, bornée pour rester lisible.
    return max(Decimal(0), min(Decimal(100), ratio)).quantize(Decimal("0.1"))
