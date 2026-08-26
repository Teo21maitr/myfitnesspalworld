"""Types de repas (spec 01 §5, spec 04 §5).

Les quatre repas par défaut sont créés **par utilisateur** plutôt que partagés.
Chacun peut alors les renommer, les réordonner et les désactiver sans affecter
les autres comptes, et les comptes déjà existants les obtiennent à leur
première visite sans reprise de données.
"""

from django.db import transaction
from django.db.models import QuerySet

from accounts.models import User
from diary.models import MealSystemKey, MealType

#: Ordre d'apparition d'une journée type.
DEFAULT_MEAL_TYPES: tuple[tuple[str, str, str], ...] = (
    (MealSystemKey.BREAKFAST, "Petit-déjeuner", "petit-dejeuner"),
    (MealSystemKey.LUNCH, "Déjeuner", "dejeuner"),
    (MealSystemKey.DINNER, "Dîner", "diner"),
    (MealSystemKey.SNACKS, "Collations", "collations"),
)


@transaction.atomic
def ensure_meal_types(user: User) -> None:
    """Crée les repas par défaut si l'utilisateur n'en a aucun.

    Volontairement idempotente et sans effet dès que l'utilisateur a pris la
    main : réactiver un repas qu'il a désactivé serait une régression de son
    point de vue.
    """
    if MealType.objects.filter(user=user).exists():
        return

    MealType.objects.bulk_create(
        [
            MealType(
                user=user,
                system_key=system_key,
                name=name,
                slug=slug,
                sort_order=index,
                is_default=True,
            )
            for index, (system_key, name, slug) in enumerate(DEFAULT_MEAL_TYPES)
        ]
    )


def meal_types_for(user: User, *, active_only: bool = False) -> QuerySet[MealType]:
    """Repas de l'utilisateur, les valeurs par défaut étant garanties."""
    ensure_meal_types(user)
    queryset = MealType.objects.filter(user=user)
    return queryset.filter(is_active=True) if active_only else queryset


@transaction.atomic
def reorder(user: User, ordered_ids: list[int]) -> None:
    """Applique un nouvel ordre. Les repas omis conservent leur rang relatif."""
    owned = {meal.id: meal for meal in MealType.objects.filter(user=user)}

    for position, meal_id in enumerate(ordered_ids):
        meal = owned.get(meal_id)
        if meal is not None:
            meal.sort_order = position
            meal.save(update_fields=["sort_order", "updated_at"])


def remove(meal_type: MealType) -> None:
    """Supprime un repas, ou le désactive s'il est système (spec 04 §5).

    Un repas comportant déjà des entrées n'est jamais supprimé non plus.
    C'est ici, et non au niveau de la base, que vit la garantie de ne pas
    perdre d'historique : une contrainte `PROTECT` bloquerait la suppression
    d'un compte tout entier.
    """
    if meal_type.is_system or meal_type.entries.exists():
        meal_type.is_active = False
        meal_type.save(update_fields=["is_active", "updated_at"])
        return

    meal_type.delete()
