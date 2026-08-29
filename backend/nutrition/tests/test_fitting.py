"""Ajustement des quantités (spec 01 §15).

Un modèle de langage choisit bien **quoi** manger et mal **combien**. Ce module
fait l'arithmétique à sa place, et ces tests vérifient qu'il la fait bien : une
composition plausible doit atteindre ses cibles, et une composition qui ne le
peut pas doit rester visiblement courte plutôt que d'être forcée.
"""

from decimal import Decimal

import pytest

from nutrition.services.fitting import MAX_FACTOR, Adjustable, fit

NUTRIENTS = {
    "daily_calories": "energy_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbohydrates_g",
    "fat_g": "fat_g",
}
TOLERANCES = {
    "daily_calories": Decimal("0.05"),
    "protein_g": Decimal("0.10"),
    "carbs_g": Decimal("0.10"),
    "fat_g": Decimal("0.10"),
}
TARGETS = {
    "daily_calories": Decimal("2000"),
    "protein_g": Decimal("100"),
    "carbs_g": Decimal("200"),
    "fat_g": Decimal("70"),
}


def per_100(quantity, *, kcal, protein, carbs, fat, unit="g") -> Adjustable:
    """Un aliment dont les valeurs sont données pour 100 unités."""
    share = Decimal(quantity) / 100
    return Adjustable(
        quantity=Decimal(quantity),
        unit_label=unit,
        values={
            "energy_kcal": share * Decimal(kcal),
            "protein_g": share * Decimal(protein),
            "carbohydrates_g": share * Decimal(carbs),
            "fat_g": share * Decimal(fat),
        },
    )


def totals(items: list[Adjustable], quantities: list[Decimal]) -> dict[str, Decimal]:
    result = dict.fromkeys(("energy_kcal", "protein_g", "carbohydrates_g", "fat_g"), Decimal(0))
    for item, quantity in zip(items, quantities, strict=True):
        scale = Decimal(quantity) / item.quantity
        for name in result:
            result[name] += Decimal(item.values[name]) * scale
    return result


def deviation(total: Decimal, target: Decimal) -> float:
    return float((total - target) / target * 100)


def adjust(items: list[Adjustable]) -> list[Decimal]:
    return fit(items, targets=TARGETS, nutrients=NUTRIENTS, tolerances=TOLERANCES)


class TestReachingTheTargets:
    def test_une_journee_trop_legere_est_remontee(self):
        # Un aliment exactement proportionnel aux cibles, servi en trop petite
        # quantité : le dosage doit le porter à 2 kg.
        items = [per_100(1400, kcal=100, protein=5, carbs=10, fat=3.5)]

        quantities = adjust(items)

        assert quantities[0] == Decimal("2000")

    def test_une_journee_trop_lourde_est_reduite(self):
        items = [per_100(3000, kcal=100, protein=5, carbs=10, fat=3.5)]

        assert adjust(items)[0] == Decimal("2000")

    def test_une_composition_desequilibree_est_rebalancee(self):
        """Ce qu'une simple mise à l'échelle ne saurait pas faire.

        Trois aliments complémentaires — protéine, glucide, lipide — servis dans
        de mauvaises proportions. Multiplier le tout par un seul facteur
        corrigerait les calories en laissant le déséquilibre intact ; le dosage
        par élément approche les quatre cibles à la fois.
        """
        items = [
            per_100(150, kcal=165, protein=31, carbs=0, fat=3.6),  # blanc de poulet
            per_100(1000, kcal=130, protein=3, carbs=28, fat=0.3),  # riz cuit
            per_100(30, kcal=900, protein=0, carbs=0, fat=100),  # huile
        ]

        avant = totals(items, [item.quantity for item in items])
        atteints = totals(items, adjust(items))

        # Le déséquilibre de départ : trop de glucides, pas assez de lipides.
        assert deviation(avant["carbohydrates_g"], TARGETS["carbs_g"]) > 30
        assert deviation(avant["fat_g"], TARGETS["fat_g"]) < -40

        for objectif, nutriment in NUTRIENTS.items():
            ecart = abs(deviation(atteints[nutriment], TARGETS[objectif]))
            assert ecart < 15, f"{objectif} à {ecart:.0f} %"

    def test_une_composition_trop_pauvre_reste_courte(self):
        """On ne force pas : dix fois la portion proposée ne serait pas un repas."""
        items = [per_100(100, kcal=100, protein=5, carbs=10, fat=3.5)]

        quantities = adjust(items)

        assert quantities[0] == Decimal("250")
        assert quantities[0] <= Decimal("100") * MAX_FACTOR


class TestHumanQuantities:
    @pytest.mark.parametrize(
        ("unit", "attendu_multiple_de"),
        [
            pytest.param("g", Decimal("5"), id="grammes"),
            pytest.param("ml", Decimal("5"), id="millilitres"),
            pytest.param("portion", Decimal("0.5"), id="portions"),
            pytest.param("unité", Decimal("0.5"), id="unités"),
        ],
    )
    def test_les_quantites_restent_servables(self, unit, attendu_multiple_de):
        """Personne ne pèse 237 g de flocons d'avoine."""
        items = [per_100(137, kcal=100, protein=5, carbs=10, fat=3.5, unit=unit)]

        quantity = adjust(items)[0]

        assert quantity % attendu_multiple_de == 0

    def test_une_petite_quantite_garde_sa_finesse(self):
        # Arrondir 12 g au pas de 5 le déformerait de moitié.
        items = [per_100(12, kcal=900, protein=0, carbs=0, fat=100)]

        assert adjust(items)[0] % Decimal("1") == 0

    def test_une_quantite_ne_tombe_jamais_a_zero(self):
        items = [per_100(1, kcal=900, protein=0, carbs=0, fat=100)]

        assert adjust(items)[0] > 0


class TestEdges:
    def test_sans_element_il_n_y_a_rien_a_ajuster(self):
        assert adjust([]) == []

    def test_sans_objectif_les_quantites_ne_bougent_pas(self):
        items = [per_100(150, kcal=100, protein=5, carbs=10, fat=3.5)]

        quantities = fit(items, targets={}, nutrients=NUTRIENTS, tolerances=TOLERANCES)

        assert quantities == [Decimal("150")]

    def test_un_objectif_nul_est_ignore(self):
        items = [per_100(1400, kcal=100, protein=5, carbs=10, fat=3.5)]

        quantities = fit(
            items,
            targets={**TARGETS, "protein_g": Decimal("0")},
            nutrients=NUTRIENTS,
            tolerances=TOLERANCES,
        )

        assert quantities[0] == Decimal("2000")

    def test_une_valeur_inconnue_ne_fait_pas_echouer_l_ajustement(self):
        """On ne peut pas optimiser contre ce qu'on ne sait pas."""
        item = per_100(1400, kcal=100, protein=5, carbs=10, fat=3.5)
        item.values["fat_g"] = None

        assert adjust([item])[0] > Decimal("1400")

    def test_un_element_sans_aucune_valeur_est_laisse_tel_quel(self):
        item = Adjustable(
            quantity=Decimal("100"), unit_label="g", values=dict.fromkeys(NUTRIENTS.values())
        )

        assert adjust([item]) == [Decimal("100")]
