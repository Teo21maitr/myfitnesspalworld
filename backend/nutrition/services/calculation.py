"""Calcul de l'objectif calorique et proposition de macros (spec 01 §3).

Le calcul est **déterministe et intégralement côté serveur** : aucune IA n'y
participe (spec 07 §1) et le frontend n'estime jamais de calories lui-même.

La spec impose « une formule métabolique standard déterministe » sans la
nommer et parle d'une « proposition macros » sans la définir : les choix
retenus sont documentés ici et restent tous remplaçables manuellement par
l'utilisateur.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from accounts.models import ActivityLevel, GoalType, SexForCalculation
from common.dates import age_on

# Mention imposée par la spec 01 §3 : l'application n'est pas un
# professionnel de santé (spec 05 §16).
ESTIMATION_NOTICE = "Il s’agit d’une estimation et non d’une recommandation médicale."

# Coefficients d'activité usuels appliqués au métabolisme de base.
ACTIVITY_FACTORS: dict[str, Decimal] = {
    ActivityLevel.SEDENTARY: Decimal("1.2"),
    ActivityLevel.LIGHTLY_ACTIVE: Decimal("1.375"),
    ActivityLevel.MODERATELY_ACTIVE: Decimal("1.55"),
    ActivityLevel.VERY_ACTIVE: Decimal("1.725"),
    ActivityLevel.EXTREMELY_ACTIVE: Decimal("1.9"),
}

# 1 kg de masse grasse vaut environ 7 700 kcal, soit 1 100 kcal par jour pour
# 1 kg par semaine.
KCAL_PER_KG_PER_DAY = Decimal("1100")

# Répartition proposée des macronutriments, en pourcentage des calories. Une
# répartition en pourcentages ne peut jamais produire de valeur négative.
MACRO_SPLITS: dict[str, dict[str, Decimal]] = {
    GoalType.LOSS: {
        "protein": Decimal("0.30"),
        "fat": Decimal("0.30"),
        "carbs": Decimal("0.40"),
    },
    GoalType.MAINTENANCE: {
        "protein": Decimal("0.25"),
        "fat": Decimal("0.30"),
        "carbs": Decimal("0.45"),
    },
    GoalType.GAIN: {
        "protein": Decimal("0.25"),
        "fat": Decimal("0.30"),
        "carbs": Decimal("0.45"),
    },
}

# Densités énergétiques (kcal par gramme).
KCAL_PER_GRAM = {
    "protein": Decimal("4"),
    "carbs": Decimal("4"),
    "fat": Decimal("9"),
}

# Seuils au-delà desquels un avertissement est affiché, sans jamais bloquer.
MINIMUM_REASONABLE_CALORIES = {
    SexForCalculation.FEMALE: Decimal("1200"),
    SexForCalculation.MALE: Decimal("1500"),
}
MAXIMUM_REASONABLE_RATE_KG_PER_WEEK = Decimal("1")
MINIMUM_REASONABLE_BMI = Decimal("18.5")


def _round(value: Decimal, places: str = "1") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def basal_metabolic_rate(*, sex: str, weight_kg: Decimal, height_cm: Decimal, age: int) -> Decimal:
    """Métabolisme de base selon Mifflin-St Jeor.

    Formule standard actuelle, plus fiable que Harris-Benedict :

        homme : 10 * poids + 6.25 * taille - 5 * age + 5
        femme : 10 * poids + 6.25 * taille - 5 * age - 161
    """
    base = Decimal("10") * weight_kg + Decimal("6.25") * height_cm - Decimal("5") * age
    offset = Decimal("5") if sex == SexForCalculation.MALE else Decimal("-161")
    return _round(base + offset)


def total_energy_expenditure(bmr: Decimal, activity_level: str) -> Decimal:
    """Dépense énergétique totale : métabolisme de base fois le coefficient d'activité."""
    return _round(bmr * ACTIVITY_FACTORS[activity_level])


def calorie_delta(goal_type: str, rate_kg_per_week: Decimal | None) -> Decimal:
    """Déficit (négatif) ou surplus (positif) quotidien lié au rythme visé.

    Le rythme est ignoré en maintien.
    """
    if goal_type == GoalType.MAINTENANCE or not rate_kg_per_week:
        return Decimal("0")

    magnitude = abs(rate_kg_per_week) * KCAL_PER_KG_PER_DAY
    return -magnitude if goal_type == GoalType.LOSS else magnitude


def daily_calorie_target(
    tdee: Decimal, goal_type: str, rate_kg_per_week: Decimal | None
) -> Decimal:
    """Objectif calorique quotidien, jamais négatif."""
    target = tdee + calorie_delta(goal_type, rate_kg_per_week)
    return _round(max(target, Decimal("0")), "1")


def suggest_macros(calories: Decimal, goal_type: str) -> dict[str, Decimal]:
    """Répartition proposée des macronutriments, en grammes.

    Les grammes sont arrondis à l'unité : la somme peut donc s'écarter de
    quelques kilocalories de l'objectif, ce que `macro_calories` permet de
    vérifier.
    """
    split = MACRO_SPLITS[goal_type]
    return {
        nutrient: _round(calories * ratio / KCAL_PER_GRAM[nutrient], "1")
        for nutrient, ratio in split.items()
    }


def macro_calories(protein_g: Decimal, carbs_g: Decimal, fat_g: Decimal) -> Decimal:
    """Calories correspondant à une répartition en grammes."""
    return _round(
        protein_g * KCAL_PER_GRAM["protein"]
        + carbs_g * KCAL_PER_GRAM["carbs"]
        + fat_g * KCAL_PER_GRAM["fat"],
        "1",
    )


def body_mass_index(weight_kg: Decimal, height_cm: Decimal) -> Decimal:
    height_m = height_cm / Decimal("100")
    return _round(weight_kg / (height_m * height_m), "0.1")


@dataclass
class CalorieEstimate:
    """Résultat complet d'un calcul, prêt à être sérialisé."""

    bmr: Decimal
    tdee: Decimal
    daily_calories: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal
    warnings: list[str] = field(default_factory=list)
    notice: str = ESTIMATION_NOTICE


def collect_warnings(
    *,
    sex: str,
    daily_calories: Decimal,
    rate_kg_per_week: Decimal | None,
    target_weight_kg: Decimal | None,
    height_cm: Decimal,
) -> list[str]:
    """Avertissements non bloquants (spec 01 §3).

    Ils signalent une valeur potentiellement déraisonnable sans jamais
    empêcher la saisie manuelle.
    """
    warnings: list[str] = []

    floor = MINIMUM_REASONABLE_CALORIES.get(sex, Decimal("1200"))
    if daily_calories < floor:
        warnings.append(
            f"L’objectif de {daily_calories:.0f} kcal est inférieur à {floor:.0f} kcal, "
            "un seuil sous lequel les apports deviennent difficiles à couvrir."
        )

    if rate_kg_per_week and abs(rate_kg_per_week) > MAXIMUM_REASONABLE_RATE_KG_PER_WEEK:
        warnings.append(
            f"Un rythme de {rate_kg_per_week} kg par semaine est ambitieux ; "
            "un rythme plus progressif est généralement mieux tenu."
        )

    if target_weight_kg:
        target_bmi = body_mass_index(target_weight_kg, height_cm)
        if target_bmi < MINIMUM_REASONABLE_BMI:
            warnings.append(
                f"Le poids cible correspond à un IMC de {target_bmi}, "
                "en dessous de la plage habituellement considérée comme normale."
            )

    return warnings


def estimate(
    *,
    sex: str,
    weight_kg: Decimal,
    height_cm: Decimal,
    birth_date: date,
    activity_level: str,
    goal_type: str,
    rate_kg_per_week: Decimal | None = None,
    target_weight_kg: Decimal | None = None,
    today: date | None = None,
) -> CalorieEstimate:
    """Chaîne complète : métabolisme de base, dépense totale, objectif et macros."""
    reference = today or date.today()
    age = age_on(birth_date, reference)

    bmr = basal_metabolic_rate(sex=sex, weight_kg=weight_kg, height_cm=height_cm, age=age)
    tdee = total_energy_expenditure(bmr, activity_level)
    calories = daily_calorie_target(tdee, goal_type, rate_kg_per_week)
    macros = suggest_macros(calories, goal_type)

    return CalorieEstimate(
        bmr=bmr,
        tdee=tdee,
        daily_calories=calories,
        protein_g=macros["protein"],
        carbs_g=macros["carbs"],
        fat_g=macros["fat"],
        warnings=collect_warnings(
            sex=sex,
            daily_calories=calories,
            rate_kg_per_week=rate_kg_per_week,
            target_weight_kg=target_weight_kg,
            height_cm=height_cm,
        ),
    )


def estimate_from_profile_data(data: dict) -> CalorieEstimate:
    """Adapte les noms de champs du profil aux paramètres de `estimate`."""
    return estimate(
        sex=data["sex_for_calculation"],
        weight_kg=data["weight_kg"],
        height_cm=data["height_cm"],
        birth_date=data["birth_date"],
        activity_level=data["activity_level"],
        goal_type=data["goal_type"],
        rate_kg_per_week=data.get("goal_rate_kg_per_week"),
        target_weight_kg=data.get("target_weight_kg"),
    )
