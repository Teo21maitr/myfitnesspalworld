"""Comptes de démonstration remplis, pour essayer l'application (CLAUDE.md §4).

Jusqu'ici, rien ne permettait de fabriquer deux comptes amis avec un journal
rempli : essayer le partage supposait de tout saisir à la main, et une
fonctionnalité qu'on n'essaie pas est une fonctionnalité qu'on ne corrige pas.

**Tout passe par les services métier.** Écrire en direct produirait des entrées
sans snapshot et des recettes au cache nul — un compte de démonstration qui ne
ressemble pas à un vrai compte ne démontre rien, et masque justement les défauts
qu'il devrait révéler.

Le jeu est tiré d'un générateur à **graine fixe** : deux exécutions donnent les
mêmes données, sans quoi un défaut observé une fois ne se reproduirait pas.
"""

import random
import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserStatus
from diary.services import entries as entries_service
from diary.services.meal_types import meal_types_for
from nutrition.models import (
    Food,
    FoodNutrition,
    FoodPortion,
    FoodSource,
    FoodVisibility,
    UserFoodFavorite,
    UserFoodHistory,
)
from nutrition.services import onboarding as onboarding_service
from planning.models import (
    ItemSource,
    MealPlan,
    MealPlanDay,
    MealPlanEntry,
    PlanEntryType,
    ShoppingList,
)
from planning.services import shopping as shopping_service
from progress.models import BodyMeasurementEntry, WeightEntry
from recipes.models import (
    ItemType,
    Recipe,
    RecipeIngredient,
    RecipeVisibility,
    SavedMeal,
    SavedMealItem,
)
from recipes.services import nutrition as recipe_nutrition
from social.models import ResourceType, SharePermission, VisibilityType
from social.services import friends as friends_service

#: Graine fixe : la démonstration doit être reproductible.
SEED = 20260829

#: Le compte principal, et ses trois relations. Chacune existe pour un cas
#: précis qu'il faut pouvoir essayer.
MAIN = "demo"
FRIENDS = {
    #: Partage tout : c'est chez elle que « Son journal » doit s'ouvrir.
    "camille": {"first_name": "Camille", "last_name": "Rivet", "shares": True},
    #: Ne partage rien : c'est lui qui prouve qu'aucun bouton n'est proposé.
    "mathis": {"first_name": "Mathis", "last_name": "Bonnet", "shares": False},
}
#: Demande d'ami en attente vers le compte principal.
PENDING = {"sofia": {"first_name": "Sofia", "last_name": "Nadir"}}

ALL_USERNAMES = [MAIN, *FRIENDS, *PENDING]

#: Journées couvertes par le journal et les pesées.
HISTORY_DAYS = 90

#: Journées volontairement laissées vides, dispersées dans la période. Elles
#: existent pour que la règle des moyennes — sur les journées **tenues** — se
#: voie à l'écran plutôt que de rester une affirmation du README.
UNLOGGED_DAYS = 12

PERSONAL_FOODS = [
    ("Granola maison", "", 430, 9.5, 58.0, 17.0, 6.4),
    ("Pain de campagne du marché", "Boulangerie Petit", 265, 8.6, 51.0, 1.2, 3.1),
    ("Skyr nature", "Arla", 63, 11.0, 4.0, 0.2, None),
    ("Barre protéinée chocolat", "Feed", 372, 30.0, 32.0, 11.0, 8.0),
    ("Houmous du traiteur", "", 306, 8.0, 14.0, 23.0, 6.0),
    ("Saumon fumé", "Labeyrie", 202, 22.5, 0.5, 12.5, None),
    ("Crêpe de sarrasin", "", 168, 5.2, 30.0, 2.6, 2.4),
    ("Café au lait", "", 42, 2.4, 4.2, 1.7, None),
]

#: Recettes composées de libellés cherchés dans le référentiel : les vrais noms
#: Ciqual varient, et une correspondance approximative vaut mieux qu'une liste
#: figée qui ne trouverait rien.
RECIPES = [
    ("Poulet rôti et pommes de terre", 4, ["poulet", "pomme de terre", "huile d'olive"]),
    ("Salade de lentilles", 3, ["lentille", "carotte", "oignon", "huile d'olive"]),
    ("Pâtes au thon", 2, ["pâtes", "thon", "tomate"]),
    ("Curry de pois chiches", 4, ["pois chiche", "riz", "oignon", "lait de coco"]),
    ("Omelette aux champignons", 2, ["oeuf", "champignon", "beurre"]),
    ("Soupe de courgettes", 4, ["courgette", "pomme de terre", "oignon"]),
]

SAVED_MEALS = [
    ("Petit-déjeuner d'entraînement", ["flocon d'avoine", "banane", "lait"]),
    ("Déjeuner rapide au bureau", ["riz", "thon", "tomate"]),
    ("Collation d'après-midi", ["amande", "pomme"]),
    ("Dîner léger", ["courgette", "oeuf"]),
]

MEAL_KEYWORDS = {
    "breakfast": ["pain", "beurre", "confiture", "yaourt", "banane", "flocon d'avoine", "lait"],
    "lunch": ["riz", "poulet", "carotte", "tomate", "pâtes", "lentille", "huile d'olive"],
    "dinner": ["saumon", "courgette", "pomme de terre", "brocoli", "oeuf", "champignon"],
    "snacks": ["pomme", "amande", "yaourt", "chocolat", "noix"],
}


class Command(BaseCommand):
    help = "Crée des comptes de démonstration remplis (usage local uniquement)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime les comptes de démonstration existants avant de les recréer.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=HISTORY_DAYS,
            help=f"Profondeur d'historique en jours (défaut : {HISTORY_DAYS}).",
        )
        parser.add_argument(
            "--password",
            help="Mot de passe des comptes. Par défaut, un mot de passe est tiré et affiché.",
        )

    def handle(self, *args, **options):
        self._refuse_in_production()
        self._require_food_reference()

        existing = User.objects.filter(username__in=ALL_USERNAMES)
        if existing.exists() and not options["reset"]:
            names = ", ".join(sorted(existing.values_list("username", flat=True)))
            raise CommandError(
                f"Ces comptes existent déjà : {names}. Relancez avec --reset pour les recréer."
            )

        # Jamais de mot de passe dans le dépôt, pas même pour un compte fictif
        # (CLAUDE.md §2). Tiré ici, affiché une fois, jamais écrit sur disque.
        password = options["password"] or secrets.token_urlsafe(9)
        history = max(7, options["days"])
        # Graine fixe, pour des données reproductibles. Rien de
        # cryptographique ici : le mot de passe, lui, vient de `secrets`.
        rng = random.Random(SEED)  # noqa: S311

        with transaction.atomic():
            existing.delete()
            accounts = self._create_accounts(password)
            self._fill(accounts[MAIN], rng, rich=True, history=history)
            for username in FRIENDS:
                # Les amis n'ont besoin que d'assez de données pour que leurs
                # écrans partagés montrent quelque chose.
                self._fill(accounts[username], rng, rich=False, history=min(history, 21))
            self._weave_social(accounts)

        self._report(password)

    # -- Garde-fous ----------------------------------------------------------

    def _refuse_in_production(self) -> None:
        """Une commande qui fabrique des comptes n'a rien à faire en production."""
        module = getattr(settings, "SETTINGS_MODULE", "") or ""
        if module.endswith("production"):
            raise CommandError(
                "Refus : cette commande crée des comptes fictifs et ne doit "
                "jamais s'exécuter avec les réglages de production."
            )

    def _require_food_reference(self) -> None:
        """Sans référentiel, le compte serait vide de tout ce qui compte."""
        if not Food.objects.filter(source=FoodSource.CIQUAL).exists():
            raise CommandError(
                "Aucun aliment Ciqual en base. Lancez d'abord `manage.py import_ciqual <dossier>`."
            )

    # -- Comptes -------------------------------------------------------------

    def _create_accounts(self, password: str) -> dict[str, User]:
        accounts = {
            MAIN: User.objects.create_user(
                username=MAIN,
                password=password,
                first_name="Alex",
                last_name="Demo",
                status=UserStatus.ACTIVE,
            )
        }

        for username, profile in {**FRIENDS, **PENDING}.items():
            accounts[username] = User.objects.create_user(
                username=username,
                password=password,
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                status=UserStatus.ACTIVE,
            )

        return accounts

    # -- Remplissage ---------------------------------------------------------

    def _fill(self, user: User, rng: random.Random, *, rich: bool, history: int) -> None:
        today = timezone.localdate()
        days = history

        # L'objectif commence au premier jour de la période : le faire
        # démarrer avant laisserait des journées sans objectif applicable.
        self._onboard(user, today - timedelta(days=days - 1))
        self._weigh(user, today, days, rng)
        # Les amis en ont besoin aussi : sans mensurations, le sélecteur de
        # métrique de la progression partagée ne montrerait jamais rien.
        self._measurements(user, today, rng)

        foods = self._personal_foods(user) if rich else []
        recipes = self._recipes(user) if rich else self._recipes(user, limit=2)
        # Proportionnel : sur une période courte, douze journées vides ne
        # laisseraient presque rien à lire.
        unlogged = round(days * (UNLOGGED_DAYS / HISTORY_DAYS)) if rich else max(1, days // 8)
        self._journal(user, today, days, rng, extra=foods, unlogged=unlogged)

        if not rich:
            return

        self._saved_meals(user)
        plan = self._meal_plan(user, today, recipes)
        self._shopping_list(user, plan)
        self._preferences(user, rng)

    def _onboard(self, user: User, start: date) -> None:
        onboarding_service.complete_onboarding(
            user,
            birth_date=date(1994, 5, 12),
            sex_for_calculation="MALE",
            height_cm=Decimal("178"),
            activity_level="MODERATELY_ACTIVE",
            goal_type="LOSS",
            goal_rate_kg_per_week=Decimal("0.5"),
            target_weight_kg=Decimal("74"),
            weight_kg=Decimal("82"),
            daily_calories=Decimal("2300"),
            protein_g=Decimal("173"),
            carbs_g=Decimal("230"),
            fat_g=Decimal("77"),
            fiber_g=Decimal("30"),
            on=start,
        )

    def _weigh(self, user: User, today: date, days: int, rng: random.Random) -> None:
        """Une pesée par jour, tendance descendante et bruit réaliste."""
        start = today - timedelta(days=days - 1)
        weight = Decimal("82.4")

        for offset in range(days):
            weight -= Decimal(str(round(rng.uniform(-0.15, 0.28), 2)))
            WeightEntry.objects.update_or_create(
                user=user,
                date=start + timedelta(days=offset),
                defaults={"weight_kg": weight.quantize(Decimal("0.1"))},
            )

    def _measurements(self, user: User, today: date, rng: random.Random) -> None:
        for week in range(8):
            day = today - timedelta(days=week * 7)
            BodyMeasurementEntry.objects.update_or_create(
                user=user,
                date=day,
                defaults={
                    "waist_cm": Decimal(str(round(88 + week * 0.4 + rng.uniform(-0.3, 0.3), 1))),
                    "chest_cm": Decimal(str(round(101 - week * 0.2, 1))),
                    "body_fat_percent": Decimal(str(round(19 + week * 0.25, 1))),
                },
            )

    def _personal_foods(self, user: User) -> list[Food]:
        created = []

        for index, (name, brand, kcal, protein, carbs, fat, fiber) in enumerate(PERSONAL_FOODS):
            food = Food.objects.create(
                source=FoodSource.USER,
                owner=user,
                name=name,
                brand=brand,
                visibility=FoodVisibility.PRIVATE,
                search_text=f"{name} {brand}".strip().casefold(),
            )
            FoodNutrition.objects.create(
                food=food,
                energy_kcal=Decimal(str(kcal)),
                protein_g=Decimal(str(protein)),
                carbohydrates_g=Decimal(str(carbs)),
                fat_g=Decimal(str(fat)),
                # Les fibres manquent sur certains produits : inconnu, jamais
                # zéro (spec 01 §8). L'écran doit pouvoir le montrer.
                fiber_g=None if fiber is None else Decimal(str(fiber)),
            )
            if index % 2 == 0:
                FoodPortion.objects.create(
                    food=food,
                    owner=user,
                    name="portion",
                    gram_equivalent=Decimal("45"),
                    is_default=False,
                    sort_order=0,
                )
            created.append(food)

        return created

    def _find(self, keyword: str) -> Food | None:
        return (
            Food.objects.filter(
                source=FoodSource.CIQUAL, name__icontains=keyword, deleted_at__isnull=True
            )
            .filter(nutrition__energy_kcal__isnull=False)
            .order_by("id")
            .first()
        )

    def _recipes(self, user: User, limit: int | None = None) -> list[Recipe]:
        created = []

        for name, servings, keywords in RECIPES[:limit]:
            ingredients = [(word, self._find(word)) for word in keywords]
            ingredients = [(word, food) for word, food in ingredients if food is not None]
            if not ingredients:
                continue

            recipe = Recipe.objects.create(
                owner=user,
                name=name,
                servings=Decimal(str(servings)),
                instructions="Tout mélanger, cuire, servir.",
                visibility=RecipeVisibility.PRIVATE,
            )
            for order, (_, food) in enumerate(ingredients):
                RecipeIngredient.objects.create(
                    recipe=recipe,
                    food=food,
                    food_name=food.name,
                    quantity=Decimal("150"),
                    unit_label="g",
                    sort_order=order,
                )

            # Par le service : un cache posé à la main serait faux dès le
            # premier ingrédient partiel.
            recipe_nutrition.refresh(recipe)
            created.append(recipe)

        return created

    def _saved_meals(self, user: User) -> None:
        for name, keywords in SAVED_MEALS:
            foods = [food for food in (self._find(word) for word in keywords) if food is not None]
            if not foods:
                continue

            meal = SavedMeal.objects.create(owner=user, name=name)
            for order, food in enumerate(foods):
                SavedMealItem.objects.create(
                    saved_meal=meal,
                    item_type=ItemType.FOOD,
                    food=food,
                    item_name=food.name,
                    quantity=Decimal("100"),
                    unit_label="g",
                    sort_order=order,
                )

    def _journal(
        self,
        user: User,
        today: date,
        days: int,
        rng: random.Random,
        *,
        extra: list[Food],
        unlogged: int,
    ) -> None:
        meals = list(meal_types_for(user).filter(is_active=True))
        by_key = {meal.system_key: meal for meal in meals if meal.system_key}
        pool = {
            key: [food for food in (self._find(word) for word in words) if food is not None]
            for key, words in MEAL_KEYWORDS.items()
        }

        start = today - timedelta(days=days - 1)
        skipped = set(rng.sample(range(days - 1), min(unlogged, days - 1)))

        for offset in range(days):
            if offset in skipped:
                continue

            day = start + timedelta(days=offset)
            for key, meal in by_key.items():
                candidates = pool.get(key) or []
                if extra and rng.random() < 0.25:
                    candidates = [*candidates, rng.choice(extra)]
                if not candidates:
                    continue

                for food in rng.sample(candidates, min(len(candidates), rng.randint(1, 3))):
                    hour = {"breakfast": 8, "lunch": 12, "dinner": 19}.get(key, 16)
                    entries_service.create_food_entry(
                        user=user,
                        food=food,
                        day=day,
                        meal_type=meal,
                        quantity=Decimal(str(rng.choice([80, 100, 120, 150, 200]))),
                        unit_label="g",
                        consumed_at=timezone.make_aware(
                            timezone.datetime(day.year, day.month, day.day, hour, 0)
                        ),
                    )

    def _meal_plan(self, user: User, today: date, recipes: list[Recipe]) -> MealPlan:
        meals = list(meal_types_for(user).filter(is_active=True))
        plan = MealPlan.objects.create(
            owner=user,
            name="Semaine à venir",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=5),
        )

        for offset in range(5):
            day = MealPlanDay.objects.create(
                meal_plan=plan, date=plan.start_date + timedelta(days=offset)
            )
            for order, meal in enumerate(meals[:3]):
                if not recipes:
                    break
                MealPlanEntry.objects.create(
                    meal_plan_day=day,
                    meal_type=meal,
                    entry_type=PlanEntryType.RECIPE,
                    recipe=recipes[(offset + order) % len(recipes)],
                    quantity=Decimal("1"),
                    unit_label="portion",
                    sort_order=order,
                )

        return plan

    def _shopping_list(self, user: User, plan: MealPlan) -> None:
        shopping = ShoppingList.objects.create(owner=user, name="Courses de la semaine")
        lines = shopping_service.lines_from_meal_plan(user, plan.id)
        if lines:
            shopping_service.add_lines(shopping, lines)
        else:
            # Un planning sans ingrédient résoluble ne doit pas rendre la liste
            # vide et muette : « du sel » est un article valable (spec 04 §11).
            shopping_service.add_lines(
                shopping,
                [
                    shopping_service.Line(
                        name="Sel",
                        food=None,
                        quantity=None,
                        unit_label=None,
                        source_type=ItemSource.MANUAL,
                    )
                ],
            )

    def _preferences(self, user: User, rng: random.Random) -> None:
        """Favoris et historique : sans eux, la recherche n'a pas de classement."""
        pool = list(
            Food.objects.filter(
                source=FoodSource.CIQUAL, nutrition__energy_kcal__isnull=False
            ).order_by("id")[:200]
        )
        if not pool:
            return

        for food in rng.sample(pool, min(8, len(pool))):
            UserFoodFavorite.objects.get_or_create(user=user, food=food)

        for food in rng.sample(pool, min(25, len(pool))):
            UserFoodHistory.objects.update_or_create(
                user=user,
                food=food,
                defaults={"last_used_at": timezone.now(), "use_count": rng.randint(1, 30)},
            )

    # -- Relations -----------------------------------------------------------

    def _weave_social(self, accounts: dict[str, User]) -> None:
        main = accounts[MAIN]

        for username in FRIENDS:
            friend = accounts[username]
            request = friends_service.send_request(from_user=friend, to_user=main)
            friends_service.accept(request=request, user=main)

            if FRIENDS[username]["shares"]:
                # Journal, progression et une recette : de quoi essayer les
                # trois écrans partagés.
                self._share(friend, main, ResourceType.DIARY)
                self._share(friend, main, ResourceType.PROGRESS)
                recipe = Recipe.objects.filter(owner=friend).order_by("id").first()
                if recipe is not None:
                    self._share(friend, main, ResourceType.RECIPE, recipe.id)
                    recipe.visibility = RecipeVisibility.SPECIFIC_USERS
                    recipe.save(update_fields=["visibility", "updated_at"])

        # Dans l'autre sens, pour que le compte principal ait aussi quelque
        # chose à révoquer.
        self._share(main, accounts["camille"], ResourceType.DIARY)

        for username in PENDING:
            friends_service.send_request(from_user=accounts[username], to_user=main)

    def _share(self, owner: User, target: User, resource_type: str, resource_id=None) -> None:
        SharePermission.objects.get_or_create(
            owner=owner,
            target_user=target,
            resource_type=resource_type,
            resource_id=resource_id,
            defaults={"visibility_type": VisibilityType.SPECIFIC_USER},
        )

    # -- Sortie --------------------------------------------------------------

    def _report(self, password: str) -> None:
        self.stdout.write(self.style.SUCCESS("Comptes de démonstration créés."))
        self.stdout.write("")
        for username in ALL_USERNAMES:
            role = {
                MAIN: "compte principal, rempli",
                "camille": "amie, partage journal + progression + recette",
                "mathis": "ami, ne partage rien",
                "sofia": "demande d'ami en attente",
            }[username]
            self.stdout.write(f"  {username:10s} — {role}")
        self.stdout.write("")
        self.stdout.write(f"  Mot de passe commun : {password}")
        self.stdout.write("")
        self.stdout.write("Il n'est affiché qu'ici : notez-le maintenant.")
