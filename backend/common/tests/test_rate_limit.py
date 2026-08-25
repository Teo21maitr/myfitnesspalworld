"""Budget d'appels partagé (spec 11 §3).

Ce compteur protège d'un dépassement collectif : les sources externes limitent
par adresse IP, et le backend n'en présente qu'une pour tous les comptes.
"""

from common.rate_limit import consume_budget, reset_budget


def test_les_appels_sont_autorises_jusqu_a_la_limite():
    autorisations = [consume_budget("essai", 3) for _ in range(3)]

    assert autorisations == [True, True, True]


def test_l_appel_de_trop_est_refuse():
    for _ in range(3):
        consume_budget("essai", 3)

    assert consume_budget("essai", 3) is False


def test_les_budgets_sont_independants():
    """Épuiser la recherche ne doit pas priver la lecture de produits."""
    for _ in range(2):
        consume_budget("recherche", 2)

    assert consume_budget("produit", 2) is True


def test_une_limite_nulle_refuse_tout():
    """Permet de couper une source par configuration."""
    assert consume_budget("essai", 0) is False


def test_la_remise_a_zero_libere_le_budget():
    for _ in range(2):
        consume_budget("essai", 2)

    reset_budget("essai")

    assert consume_budget("essai", 2) is True
