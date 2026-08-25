"""Utilitaires de dates partagés."""

from datetime import date


def age_on(birth_date: date, reference: date) -> int:
    """Âge révolu à une date de référence."""
    years = reference.year - birth_date.year
    if (reference.month, reference.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years
