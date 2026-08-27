"""Champs nutritionnels partagés (spec 01 §4, spec 03 §3).

Les mêmes vingt nutriments décrivent un aliment et une recette. Les écrire deux
fois ferait diverger deux tables censées rester interchangeables : le journal
recopie l'une ou l'autre dans le même jeu de colonnes de snapshot.

Modèle **abstrait** : aucune table, aucune migration sur les modèles qui en
héritent tant que les champs restent identiques.
"""

from django.db import models


class NutrientValues(models.Model):
    """Valeurs nutritionnelles pour une quantité de référence.

    Tous les champs sont nullables : une donnée absente de la source reste
    absente, elle n'est jamais remplacée par zéro (spec 01 §8).
    """

    energy_kcal = models.DecimalField(
        "énergie (kcal)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    protein_g = models.DecimalField(
        "protéines (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    carbohydrates_g = models.DecimalField(
        "glucides (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    fat_g = models.DecimalField(
        "lipides (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    fiber_g = models.DecimalField(
        "fibres (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    sugars_g = models.DecimalField(
        "sucres (g)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    sodium_mg = models.DecimalField(
        "sodium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    salt_g = models.DecimalField("sel (g)", max_digits=9, decimal_places=3, null=True, blank=True)
    cholesterol_mg = models.DecimalField(
        "cholestérol (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    potassium_mg = models.DecimalField(
        "potassium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    calcium_mg = models.DecimalField(
        "calcium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    iron_mg = models.DecimalField("fer (mg)", max_digits=9, decimal_places=3, null=True, blank=True)
    magnesium_mg = models.DecimalField(
        "magnésium (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_a_ug = models.DecimalField(
        "vitamine A (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_b6_mg = models.DecimalField(
        "vitamine B6 (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_b12_ug = models.DecimalField(
        "vitamine B12 (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_c_mg = models.DecimalField(
        "vitamine C (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_d_ug = models.DecimalField(
        "vitamine D (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_e_mg = models.DecimalField(
        "vitamine E (mg)", max_digits=9, decimal_places=3, null=True, blank=True
    )
    vitamin_k_ug = models.DecimalField(
        "vitamine K (µg)", max_digits=9, decimal_places=3, null=True, blank=True
    )

    class Meta:
        abstract = True

    @property
    def net_carbs_g(self):
        """Glucides nets = glucides - fibres (spec 01 §4).

        Reste inconnu si l'une des deux valeurs manque.
        """
        if self.carbohydrates_g is None or self.fiber_g is None:
            return None
        return self.carbohydrates_g - self.fiber_g


#: Noms des nutriments, dans l'ordre de déclaration.
NUTRIENT_FIELDS = tuple(field.name for field in NutrientValues._meta.fields if field.name != "id")
