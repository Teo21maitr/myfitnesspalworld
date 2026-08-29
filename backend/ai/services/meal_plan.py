"""Meal Planner : de la proposition du modèle à un plan qui tient (spec 01 §15).

Ce module porte la règle qui donne son sens à l'étape :

> **La tolérance se mesure sur les fiches, jamais sur les dires du modèle.**

Le modèle ne pèse rien. Il propose « riz, 200 g » ; ce que 200 g de ce riz-là
valent est dans la base, et peut s'écarter de son estimation d'un tiers. On ne
lui demande donc aucun chiffre nutritionnel — le schéma n'en prévoit pas — et
les totaux sont recalculés à partir des fiches retrouvées. C'est sur eux, et
sur eux seuls, que l'écart aux objectifs est mesuré.

**Une journée à la fois.** Mesuré contre l'API : une semaine entière dépasse
16 000 jetons de réponse et revient tronquée après plus de deux minutes, quand
une journée en tient 1 100 en onze secondes. Le découpage n'est pas qu'une
affaire de budget — il rend chaque correction locale, un jour hors tolérance se
rejouant seul, et il colle aux cibles de la spec, qui sont journalières.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings

from ai import prompts, schemas
from ai.providers import AIResponseUnusable
from ai.services.ai_service import AIService
from nutrition.models import Food
from nutrition.models.nutrients import NUTRIENT_FIELDS
from nutrition.services.aggregation import sum_values
from nutrition.services.fitting import Adjustable, fit
from nutrition.services.quantities import available_units
from nutrition.services.search import search_foods
from recipes.models import Recipe
from recipes.services.nutrition import ensure_fresh, ingredient_values

logger = logging.getLogger(__name__)

#: Tolérances de la spec 01 §15 : ±5 % sur les calories, ±10 % sur les macros.
TOLERANCES: dict[str, Decimal] = {
    "daily_calories": Decimal("0.05"),
    "protein_g": Decimal("0.10"),
    "carbs_g": Decimal("0.10"),
    "fat_g": Decimal("0.10"),
}

#: Nom du nutriment correspondant à chaque objectif.
TARGET_NUTRIENT = {
    "daily_calories": "energy_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbohydrates_g",
    "fat_g": "fat_g",
}

#: Plafond dur (spec 07 §7). Sans lui, une journée impossible à satisfaire
#: appellerait le fournisseur indéfiniment.
MAX_ATTEMPTS = 3

#: Budget d'une journée.
#:
#: Le texte utile tient en ~1 300 caractères, mais **les jetons de réflexion
#: s'imputent sur le même budget** : mesuré à 1 800 jetons de sortie sur un
#: prompt court, davantage quand la matière fournie s'allonge. Un budget trop
#: serré coupe la réponse en plein JSON — d'où cette marge de quatre fois.
DAY_MAX_TOKENS = 8192

#: Composer un menu n'est pas une tâche de raisonnement profond : le schéma en
#: impose déjà la structure, et l'arithmétique nutritionnelle revient à la base,
#: pas au modèle. Mesuré à qualité de sortie égale : 6 s contre 16, et trois
#: fois moins de jetons. Sur une semaine où chaque jour peut coûter trois
#: essais, la différence décide si la tâche tient dans le temps imparti.
DAY_EFFORT = "low"

#: Combien d'aliments récents proposer au modèle comme matière.
FREQUENT_LIMIT = 30


@dataclass
class _Portion:
    """Duck-type d'ingrédient.

    `ingredient_values` n'attend que ces trois attributs : le réutiliser évite
    d'écrire une troisième fois la multiplication d'une quantité par son facteur.
    """

    food: Food | None
    quantity: Decimal
    unit_label: str


@dataclass
class ResolvedItem:
    """Un élément du plan, retrouvé dans la base."""

    meal_name: str
    entry_type: str
    label: str
    quantity: Decimal
    unit_label: str
    values: dict[str, Decimal | None]
    food: Food | None = None
    recipe: Recipe | None = None
    #: Recette proposée par le modèle, pas encore enregistrée.
    proposed_recipe: "ProposedRecipe | None" = None


@dataclass
class ResolvedDay:
    """Une journée résolue, avec ses totaux réels et son écart aux objectifs."""

    date: str
    items: list[ResolvedItem]
    totals: dict[str, Decimal | None]
    deviations: dict[str, float]
    #: Libellés que la base n'a pas su retrouver, nommés plutôt qu'inventés.
    unmatched: list[str] = field(default_factory=list)
    #: Nombre d'appels au fournisseur qu'a coûté cette journée — pas le rang de
    #: la tentative retenue : c'est la dépense qui intéresse, et le signe qu'une
    #: journée a été difficile.
    attempts: int = 1

    @property
    def within_tolerance(self) -> bool:
        return within_tolerance(self.deviations)

    @property
    def worst_deviation(self) -> float:
        return max((abs(value) for value in self.deviations.values()), default=0.0)


def within_tolerance(deviations: dict[str, float]) -> bool:
    """Toutes les mesures sont-elles dans leur tolérance ?"""
    return all(
        abs(deviations[name]) <= float(TOLERANCES[name]) * 100
        for name in deviations
        if name in TOLERANCES
    )


def deviations_from(totals: dict[str, Decimal | None], targets: dict) -> dict[str, float]:
    """Écart relatif de chaque objectif, en pourcentage.

    Un objectif absent ou nul est ignoré : diviser par zéro n'apprendrait rien,
    et un objectif qu'on ne s'est pas fixé n'a pas d'écart.
    """
    measured: dict[str, float] = {}

    for name, nutrient in TARGET_NUTRIENT.items():
        target = targets.get(name)
        total = totals.get(nutrient)
        if target is None or Decimal(target) == 0 or total is None:
            continue
        measured[name] = float((Decimal(total) - Decimal(target)) / Decimal(target) * 100)

    return measured


def _usable_unit(food: Food, unit: str) -> str:
    """Unité que l'aliment sait convertir, son unité de référence sinon.

    Même arbitrage que Meal Scan : une unité incalculable ferait échouer la
    suite pour un choix que l'utilisateur n'a pas fait (spec 01 §9).
    """
    return unit if unit in available_units(food) else food.reference_unit


def _resolve_food(user, label: str) -> Food | None:
    """Meilleure correspondance dans le référentiel, par la recherche ordinaire.

    La même que celle du champ de recherche : un plan ne doit pas puiser dans
    un référentiel différent de celui que l'utilisateur voit.
    """
    return search_foods(user, label).prefetch_related("portions").first()


@dataclass
class ProposedRecipe:
    """Recette inédite, dont les ingrédients ont été retrouvés en base.

    Elle n'est pas enregistrée : elle voyage avec la proposition de plan et ne
    devient une recette qu'à l'acceptation (spec 07 §8).
    """

    name: str
    servings: Decimal
    instructions: str
    #: `(food, quantité, unité)`, les seuls ingrédients retrouvés.
    ingredients: list[tuple[Food, Decimal, str]]
    per_serving: dict[str, Decimal | None]
    unmatched: list[str]


def _resolve_proposed_recipe(user, proposal: dict) -> ProposedRecipe:
    """Retrouve les ingrédients d'une recette proposée et calcule sa nutrition.

    Le modèle ne fournit aucune valeur nutritionnelle : elle se déduit des
    ingrédients retrouvés en base, exactement comme pour une recette
    enregistrée (spec 07 §8).
    """
    ingredients: list[tuple[Food, Decimal, str]] = []
    unmatched: list[str] = []

    for ingredient in proposal["ingredients"]:
        food = _resolve_food(user, ingredient["label"])
        if food is None:
            unmatched.append(ingredient["label"])
            continue
        ingredients.append(
            (food, Decimal(ingredient["quantity"]), _usable_unit(food, ingredient["unit"]))
        )

    portions = [_Portion(food, quantity, unit) for food, quantity, unit in ingredients]
    totals, _ = sum_values((ingredient_values(portion) for portion in portions), NUTRIENT_FIELDS)
    servings = Decimal(proposal["servings"])

    return ProposedRecipe(
        name=proposal["name"],
        servings=servings,
        instructions=proposal.get("instructions", ""),
        ingredients=ingredients,
        per_serving={
            name: None if value is None else value / servings for name, value in totals.items()
        },
        unmatched=unmatched,
    )


def _per_serving(nutrition) -> dict[str, Decimal | None]:
    """Valeurs d'une portion, lues sur le cache d'une recette enregistrée."""
    return {name: getattr(nutrition, name, None) for name in NUTRIENT_FIELDS}


def _recipe_item_values(per_serving: dict[str, Decimal | None], servings: Decimal) -> dict:
    """Apport de N portions d'une recette."""
    return {
        name: None if value is None else Decimal(value) * servings
        for name, value in per_serving.items()
    }


def resolve_day(user, day_payload: dict, proposed_recipes: dict[str, dict]) -> ResolvedDay:
    """Retrouve chaque élément proposé dans la base et recalcule les totaux.

    C'est ici que la proposition du modèle cesse d'être une intention : ce qui
    ne se retrouve pas est **nommé et écarté**, jamais approximé, et les valeurs
    retenues sont celles des fiches.
    """
    items: list[ResolvedItem] = []
    unmatched: list[str] = []

    existing_recipes = {
        recipe.name.casefold(): recipe for recipe in Recipe.objects.visible_to(user).active()
    }

    for meal in day_payload["meals"]:
        for raw in meal["items"]:
            label = raw["label"]
            quantity = Decimal(raw["quantity"])

            if raw["type"] == schemas.PLAN_ITEM_TYPES[1]:
                recipe = existing_recipes.get(label.casefold())
                if recipe is not None:
                    per_serving = _per_serving(ensure_fresh(recipe))
                    items.append(
                        ResolvedItem(
                            meal_name=meal["meal"],
                            entry_type="recipe",
                            label=recipe.name,
                            quantity=quantity,
                            unit_label="portion",
                            values=_recipe_item_values(per_serving, quantity),
                            recipe=recipe,
                        )
                    )
                    continue

                proposal = proposed_recipes.get(label.casefold())
                if proposal is None:
                    # Une recette annoncée mais jamais décrite ne mène nulle part.
                    unmatched.append(label)
                    continue

                proposed = _resolve_proposed_recipe(user, proposal)
                unmatched.extend(proposed.unmatched)
                if not proposed.ingredients:
                    # Une recette dont aucun ingrédient ne se retrouve n'a ni
                    # nutrition ni ligne de courses : elle est écartée, nommée.
                    unmatched.append(proposed.name)
                    continue

                items.append(
                    ResolvedItem(
                        meal_name=meal["meal"],
                        entry_type="recipe",
                        label=proposed.name,
                        quantity=quantity,
                        unit_label="portion",
                        values=_recipe_item_values(proposed.per_serving, quantity),
                        proposed_recipe=proposed,
                    )
                )
                continue

            food = _resolve_food(user, label)
            if food is None:
                unmatched.append(label)
                continue

            unit = _usable_unit(food, raw["unit"])
            items.append(
                ResolvedItem(
                    meal_name=meal["meal"],
                    entry_type="food",
                    label=food.name,
                    quantity=quantity,
                    unit_label=unit,
                    values=ingredient_values(_Portion(food, quantity, unit)),
                    food=food,
                )
            )

    totals, _ = sum_values((item.values for item in items), NUTRIENT_FIELDS)

    return ResolvedDay(
        date=day_payload["date"].isoformat(),
        items=items,
        totals=totals,
        deviations={},
        unmatched=sorted(set(unmatched)),
    )


def apply_fit(day: ResolvedDay, targets: dict) -> None:
    """Ajuste les quantités de la journée pour approcher les objectifs.

    Le modèle a choisi **quoi** manger ; le dosage revient au backend, qui sait
    le calculer exactement. Sans cette étape, viser quatre cibles à la fois
    tenait de la devinette : mesuré, les journées sortaient à 20 % et trois
    corrections successives n'y changeaient pas grand-chose.

    Ce qui reste hors tolérance après ajustement ne se corrige plus par les
    quantités : c'est la **composition** qu'il faut changer, et c'est cela qu'on
    redemande au modèle.
    """
    if not day.items:
        return

    adjustables = [
        Adjustable(quantity=item.quantity, unit_label=item.unit_label, values=item.values)
        for item in day.items
    ]
    quantities = fit(adjustables, targets=targets, nutrients=TARGET_NUTRIENT, tolerances=TOLERANCES)

    for item, quantity in zip(day.items, quantities, strict=True):
        if item.quantity == 0:
            continue
        # Les valeurs sont linéaires en la quantité : la mise à l'échelle suffit,
        # inutile de repasser par les fiches.
        scale = Decimal(quantity) / Decimal(item.quantity)
        item.quantity = quantity
        item.values = {
            name: None if value is None else Decimal(value) * scale
            for name, value in item.values.items()
        }

    day.totals, _ = sum_values((item.values for item in day.items), NUTRIENT_FIELDS)


def _measured_items(day: ResolvedDay) -> list[tuple[str, str, str]]:
    """Ce que chaque quantité proposée valait réellement, d'après la base.

    Les macros y figurent, pas seulement les calories : un modèle à qui l'on
    reproche un excès de lipides sans lui dire d'où il vient corrige à
    l'aveugle. Mesuré — sans elles, l'écart sur les lipides ne descendait pas
    sous +28 % en trois essais.
    """

    def montant(name: str, values: dict) -> str:
        value = values.get(name)
        return "?" if value is None else f"{value:.0f}"

    return [
        (
            item.label,
            f"{item.quantity:.0f} {item.unit_label}",
            f"{montant('energy_kcal', item.values)} kcal, "
            f"P {montant('protein_g', item.values)} / "
            f"G {montant('carbohydrates_g', item.values)} / "
            f"L {montant('fat_g', item.values)}",
        )
        for item in day.items
    ]


def generate_day(
    *,
    service,
    user,
    day,
    targets: dict,
    meal_names: list[str],
    constraints: dict,
    materials: dict,
    already_planned: list[str],
) -> ResolvedDay:
    """Compose une journée, en corrigeant tant qu'elle sort des tolérances.

    Trois essais au maximum (spec 07 §7). Au-delà, la meilleure des tentatives
    est rendue telle quelle : l'appelant l'assortira d'un avertissement plutôt
    que de faire échouer tout un plan pour une journée difficile.

    L'écart renvoyé au modèle est celui **mesuré sur les fiches**. Lui renvoyer
    ses propres estimations ne corrigerait rien.
    """
    feedback: str | None = None
    best: ResolvedDay | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = prompts.meal_plan_prompt(
            day=day.isoformat(),
            targets=targets,
            meal_names=meal_names,
            allergies=constraints.get("allergies", []),
            liked=constraints.get("liked", []),
            disliked=constraints.get("disliked", []),
            recipes=materials.get("recipes", []),
            frequent=materials.get("frequent", []),
            already_planned=already_planned,
            feedback=feedback,
        )

        payload = service.generate_meal_plan(
            user=user,
            prompt=prompt,
            meal_names=meal_names,
            dates=[day.isoformat()],
            model=settings.AI_MEAL_PLANNER_MODEL or settings.AI_MEAL_SCAN_MODEL,
        )

        proposed = {recipe["name"].casefold(): recipe for recipe in payload["recipes"]}
        first_day = payload["days"][0] if payload["days"] else {"date": day, "meals": []}
        resolved = resolve_day(user, first_day, proposed)
        resolved.date = day.isoformat()
        # Le dosage avant la mesure : c'est la composition qu'on évalue, pas la
        # capacité du modèle à faire des multiplications.
        apply_fit(resolved, targets)
        resolved.deviations = deviations_from(resolved.totals, targets)
        resolved.attempts = attempt

        if best is None or resolved.worst_deviation < best.worst_deviation:
            best = resolved

        if resolved.within_tolerance:
            return resolved

        feedback = prompts.deviation_feedback(
            resolved.deviations, targets, measured=_measured_items(resolved)
        )

    logger.info(
        "Journée %s rendue hors tolérance après %s essais (écart max %.0f %%)",
        day,
        MAX_ATTEMPTS,
        best.worst_deviation if best else 0,
    )
    if best is None:  # pragma: no cover - la boucle produit toujours un résultat
        raise AIResponseUnusable("Aucune journée n'a pu être composée.")

    # La meilleure tentative sort, mais elle a coûté tous les essais.
    best.attempts = MAX_ATTEMPTS
    return best


def _values_summary(values: dict[str, Decimal | None]) -> dict[str, str | None]:
    """Les quatre macros d'un élément, en chaînes — le reste n'est pas affiché."""
    return {
        name: None if values.get(name) is None else str(values[name])
        for name in ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")
    }


def _recipe_payload(recipe: ProposedRecipe) -> dict:
    """Recette proposée, telle que le frontend la renverra pour l'enregistrer."""
    return {
        "name": recipe.name,
        "servings": str(recipe.servings),
        "instructions": recipe.instructions,
        "ingredients": [
            {
                "food_id": food.pk,
                "label": food.name,
                "quantity": str(quantity),
                "unit_label": unit,
            }
            for food, quantity, unit in recipe.ingredients
        ],
    }


def day_payload(day: ResolvedDay, *, targets: dict, meal_ids: dict[str, int]) -> dict:
    """Journée résolue, sous la forme que le frontend affiche et renvoie.

    Les écarts sont ceux mesurés sur les fiches : c'est le chiffre que
    l'utilisateur doit voir, et le seul qui ait servi à décider.
    """
    from ai.serializers import FoodCandidateSerializer

    meals: dict[str, dict] = {}

    for item in day.items:
        meal = meals.setdefault(
            item.meal_name,
            {"meal": item.meal_name, "meal_type_id": meal_ids.get(item.meal_name), "items": []},
        )

        payload = {
            "entry_type": item.entry_type,
            "label": item.label,
            "quantity": str(item.quantity),
            "unit_label": item.unit_label,
            "values": _values_summary(item.values),
        }

        if item.food is not None:
            payload["food"] = FoodCandidateSerializer(item.food).data
        elif item.recipe is not None:
            payload["recipe_id"] = item.recipe.pk
        elif item.proposed_recipe is not None:
            payload["new_recipe"] = _recipe_payload(item.proposed_recipe)

        meal["items"].append(payload)

    return {
        "date": day.date,
        "targets": {name: str(value) for name, value in targets.items() if value is not None},
        "totals": _values_summary(day.totals),
        "deviations": {name: round(value, 1) for name, value in day.deviations.items()},
        "within_tolerance": day.within_tolerance,
        "attempts": day.attempts,
        "unmatched": day.unmatched,
        "meals": list(meals.values()),
    }


def _materials(user) -> dict[str, list[str]]:
    """Ce dans quoi le modèle peut puiser, nommé.

    Ses propres recettes et ses aliments fréquents : un plan composé
    exclusivement d'inconnus serait juste sur le papier et jamais cuisiné.
    """
    from nutrition.services.search import frequent_foods

    return {
        "recipes": list(
            Recipe.objects.filter(owner=user, deleted_at__isnull=True).values_list(
                "name", flat=True
            )
        ),
        "frequent": list(frequent_foods(user, limit=FREQUENT_LIMIT).values_list("name", flat=True)),
    }


def build_proposal(*, user, constraints: dict, on_progress=None) -> dict:
    """Compose la proposition de plan, une journée après l'autre.

    Rien n'est persisté : c'est une proposition. `POST /meal-plans/` écrira ce
    que l'utilisateur aura relu — même règle qu'à l'étape 12, les endpoints IA
    suggèrent et un endpoint ordinaire enregistre.
    """
    from datetime import timedelta

    from diary.models import MealType
    from nutrition.services.goals import resolve_for_date

    service = AIService()

    meals = list(
        MealType.objects.filter(
            user=user, is_active=True, pk__in=constraints["meal_type_ids"]
        ).order_by("sort_order", "id")
    )
    if not meals:
        raise AIResponseUnusable("Aucun repas à remplir.")

    meal_names = [meal.name for meal in meals]
    meal_ids = {meal.name: meal.pk for meal in meals}
    materials = _materials(user)

    start, end = constraints["start_date"], constraints["end_date"]
    dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]

    days: list[dict] = []
    warnings: list[str] = []
    already_planned: list[str] = []

    for index, day in enumerate(dates):
        # Chaque jour a sa propre cible : la surcharge de jour de semaine
        # existe précisément pour ça (spec 01 §4).
        targets = resolve_for_date(user, day)
        if targets is None:
            raise AIResponseUnusable(
                "Aucun objectif nutritionnel n'est défini : impossible de composer un plan."
            )

        resolved = generate_day(
            service=service,
            user=user,
            day=day,
            targets=targets,
            meal_names=meal_names,
            constraints=constraints,
            materials=materials,
            already_planned=already_planned[-12:],
        )

        days.append(day_payload(resolved, targets=targets, meal_ids=meal_ids))
        already_planned.extend(item.label for item in resolved.items)

        if not resolved.within_tolerance:
            warnings.append(
                f"Le {day.strftime('%d/%m')} reste à {resolved.worst_deviation:.0f} % "
                f"de l'objectif après {resolved.attempts} essais."
            )
        if resolved.unmatched:
            warnings.append(
                f"Le {day.strftime('%d/%m')}, non retrouvés en base : "
                f"{', '.join(resolved.unmatched)}."
            )

        if on_progress is not None:
            on_progress(index + 1, len(dates))

    return {
        "name": constraints.get("name") or f"Semaine du {start.strftime('%d/%m')}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": days,
        "warnings": warnings,
    }


def regenerate_meal(*, user, plan_id: int, day_id: int, meal_type_id: int) -> dict:
    """Recompose un repas d'un plan enregistré, et remplace ses entrées.

    La cible visée est **la part de la journée** revenant à ce repas : sans
    objectif par repas dans le modèle de données (spec 03 §2), on répartit à
    parts égales entre les repas de la journée. C'est une approximation
    assumée, et la seule qui n'invente pas de règle métier.

    Les recettes inventées sont écartées : elles ne s'enregistrent qu'à
    l'acceptation d'un plan.
    """
    from django.db import transaction

    from diary.models import MealType
    from nutrition.services.goals import resolve_for_date
    from planning.models import MealPlanDay, MealPlanEntry, PlanEntryType

    day = MealPlanDay.objects.filter(
        pk=day_id, meal_plan__pk=plan_id, meal_plan__owner=user
    ).first()
    meal = MealType.objects.filter(pk=meal_type_id, user=user).first()
    if day is None or meal is None:
        raise AIResponseUnusable("Ce repas n'appartient pas à ce planning.")

    targets = resolve_for_date(user, day.date)
    if targets is None:
        raise AIResponseUnusable("Aucun objectif nutritionnel n'est défini.")

    meals_in_day = day.entries.values("meal_type_id").distinct().count() or 1
    share = Decimal(meals_in_day)
    scaled = {
        name: (Decimal(value) / share if value is not None else None)
        for name, value in targets.items()
        if name in TARGET_NUTRIENT
    }

    resolved = generate_day(
        service=AIService(),
        user=user,
        day=day.date,
        targets=scaled,
        meal_names=[meal.name],
        constraints={},
        materials=_materials(user),
        already_planned=[],
    )

    kept = [item for item in resolved.items if item.proposed_recipe is None]
    dropped = [item.label for item in resolved.items if item.proposed_recipe is not None]

    with transaction.atomic():
        day.entries.filter(meal_type=meal).delete()
        MealPlanEntry.objects.bulk_create(
            MealPlanEntry(
                meal_plan_day=day,
                meal_type=meal,
                entry_type=PlanEntryType.FOOD if item.food else PlanEntryType.RECIPE,
                food=item.food,
                recipe=item.recipe,
                quantity=item.quantity,
                unit_label=item.unit_label,
                sort_order=index,
                generated_by_ai=True,
            )
            for index, item in enumerate(kept)
        )

    return {
        "day_id": day.pk,
        "meal_type_id": meal.pk,
        "replaced": len(kept),
        "dropped_recipes": dropped,
        "unmatched": resolved.unmatched,
        "attempts": resolved.attempts,
    }
