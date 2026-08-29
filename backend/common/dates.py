"""Utilitaires de dates partagés."""

from datetime import date, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError


def age_on(birth_date: date, reference: date) -> int:
    """Âge révolu à une date de référence."""
    years = reference.year - birth_date.year
    if (reference.month, reference.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def parse_iso_date(raw: str | None, field: str) -> date | None:
    """Date d'un paramètre de requête, `None` s'il est absent."""
    if not raw:
        return None

    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise ValidationError({field: "Date invalide. Format attendu : AAAA-MM-JJ."}) from error


def parse_period(
    raw_from: str | None,
    raw_to: str | None,
    *,
    default_days: int,
    max_days: int,
) -> tuple[date, date]:
    """Intervalle demandé, borné pour que la réponse reste finie.

    Partagé par les courbes, l'analyse et les rapports : trois lectures de la
    même période ne doivent pas retenir trois intervalles différents selon
    l'endpoint interrogé.
    """
    end = parse_iso_date(raw_to, "to") or timezone.localdate()
    start = parse_iso_date(raw_from, "from") or end - timedelta(days=default_days - 1)

    if start > end:
        raise ValidationError({"from": "La date de début doit précéder la date de fin."})

    if (end - start).days + 1 > max_days:
        années = max_days // 365
        raise ValidationError({"from": f"Période trop longue : {années} an(s) au maximum."})

    return start, end
