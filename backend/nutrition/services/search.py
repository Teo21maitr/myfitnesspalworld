"""Recherche d'aliments (spec 01 §7).

La recherche est entièrement résolue par PostgreSQL : filtrage, score et tri
se font en une requête, jamais en Python. L'index trigramme posé sur
`search_text` sert à la fois au `LIKE '%…%'` et au calcul de similarité, ce
qui rend la recherche tolérante aux fautes tout en restant instantanée.

Aucune IA n'intervient : une recherche normale est déterministe (spec 01 §7).
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import (
    Case,
    DecimalField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.utils import timezone

from accounts.models import User
from nutrition.models import (
    Food,
    FoodSource,
    UserFoodFavorite,
    UserFoodHistory,
    normalize_search_text,
)

#: La recherche ne se déclenche qu'à partir de deux caractères (spec 01 §7).
MINIMUM_QUERY_LENGTH = 2

#: En deçà, la similarité relève du bruit plutôt que de la faute de frappe.
SIMILARITY_THRESHOLD = 0.15

#: Départage deux résultats par ailleurs équivalents. Les fiches officielles
#: passent devant les produits collaboratifs, eux-mêmes devant les fiches
#: créées par d'autres utilisateurs.
SOURCE_WEIGHTS = {
    FoodSource.CIQUAL: 3,
    FoodSource.OFF: 2,
    FoodSource.USER: 1,
    FoodSource.GENERATED: 0,
}


def annotate_personal_signals(queryset: QuerySet, user: User) -> QuerySet:
    """Ajoute favori, dernière utilisation et fréquence pour cet utilisateur."""
    history = UserFoodHistory.objects.filter(user=user, food=OuterRef("pk"))

    return queryset.annotate(
        is_favorite=Exists(UserFoodFavorite.objects.filter(user=user, food=OuterRef("pk"))),
        last_used_at=Subquery(history.values("last_used_at")[:1]),
        use_count=Subquery(history.values("use_count")[:1]),
    )


def _source_weight_expression():
    return Case(
        *[When(source=source, then=Value(weight)) for source, weight in SOURCE_WEIGHTS.items()],
        default=Value(0),
        output_field=IntegerField(),
    )


def search_foods(user: User, query: str) -> QuerySet:
    """Aliments correspondant à la requête, classés selon la spec 01 §7.

    L'ordre est : favoris, récents, fréquents, correspondance exacte,
    correspondance par préfixe, similarité, puis pondération de source.

    Une requête trop courte ne renvoie rien : c'est au frontend d'afficher les
    favoris, récents et fréquents tant que l'utilisateur n'a pas assez saisi.
    """
    normalized = normalize_search_text(query)
    if len(normalized) < MINIMUM_QUERY_LENGTH:
        return Food.objects.none()

    queryset = annotate_personal_signals(
        Food.objects.visible_to(user).select_related("nutrition"), user
    )

    queryset = queryset.annotate(
        similarity=TrigramSimilarity("search_text", normalized),
        is_exact=Case(
            When(search_text=normalized, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        is_prefix=Case(
            When(search_text__startswith=normalized, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        source_weight=_source_weight_expression(),
    )

    # Le `icontains` capte les correspondances littérales, y compris sur les
    # requêtes courtes où la similarité trigramme reste faible ; la similarité
    # rattrape les fautes de frappe. Les deux s'appuient sur le même index.
    queryset = queryset.filter(
        Q(search_text__icontains=normalized)
        | Q(similarity__gte=Value(SIMILARITY_THRESHOLD, output_field=DecimalField()))
    )

    return queryset.order_by(
        F("is_favorite").desc(),
        F("last_used_at").desc(nulls_last=True),
        F("use_count").desc(nulls_last=True),
        F("is_exact").desc(),
        F("is_prefix").desc(),
        F("similarity").desc(),
        F("source_weight").desc(),
        "name",
    )


def recent_foods(user: User, limit: int = 50) -> QuerySet:
    """Derniers aliments distincts utilisés (spec 01 §7)."""
    recent_ids = UserFoodHistory.objects.filter(user=user).order_by("-last_used_at")[:limit]

    return (
        Food.objects.visible_to(user)
        .select_related("nutrition")
        .filter(pk__in=[entry.food_id for entry in recent_ids])
        .annotate(
            last_used_at=Subquery(
                UserFoodHistory.objects.filter(user=user, food=OuterRef("pk")).values(
                    "last_used_at"
                )[:1]
            )
        )
        .order_by(F("last_used_at").desc(nulls_last=True))
    )


def frequent_foods(user: User, limit: int = 50) -> QuerySet:
    """Aliments les plus utilisés, calculés à partir de `use_count`."""
    frequent_ids = UserFoodHistory.objects.filter(user=user).order_by("-use_count")[:limit]

    return (
        Food.objects.visible_to(user)
        .select_related("nutrition")
        .filter(pk__in=[entry.food_id for entry in frequent_ids])
        .annotate(
            use_count=Subquery(
                UserFoodHistory.objects.filter(user=user, food=OuterRef("pk")).values("use_count")[
                    :1
                ]
            )
        )
        .order_by(F("use_count").desc(nulls_last=True))
    )


def favorite_foods(user: User) -> QuerySet:
    """Aliments marqués d'une étoile."""
    return (
        Food.objects.visible_to(user)
        .select_related("nutrition")
        .filter(favorited_by__user=user)
        .order_by("-favorited_by__created_at")
    )


def record_food_usage(user: User, food: Food) -> UserFoodHistory:
    """Enregistre l'usage d'un aliment.

    Appelée à chaque ajout au journal : c'est elle qui alimente les listes
    « récents » et « fréquents » ainsi que le classement de la recherche.
    """
    history, created = UserFoodHistory.objects.get_or_create(
        user=user, food=food, defaults={"last_used_at": timezone.now()}
    )

    if not created:
        history.use_count = F("use_count") + 1
        history.last_used_at = timezone.now()
        history.save(update_fields=["use_count", "last_used_at"])
        history.refresh_from_db()

    return history
