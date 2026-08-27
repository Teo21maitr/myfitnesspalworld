"""Fixtures des tests d'IA."""

from decimal import Decimal

import pytest

from accounts.models import User, UserStatus
from ai.providers import AIProviderUnavailable, ImagePart
from nutrition.models import Food, FoodNutrition, FoodPortion, FoodSource

#: Un JPEG minimal : signature valide, contenu sans importance.
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class StubProvider:
    """Fournisseur pilotable, pour éprouver chaque branche.

    `payload` est renvoyé tel quel — y compris mal formé. `error` est levée à
    la place, pour simuler une panne.
    """

    name = "stub"

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict] = []

    def structured_completion(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.fixture
def stub_provider():
    return StubProvider


@pytest.fixture
def unavailable_provider():
    return StubProvider(error=AIProviderUnavailable("Le fournisseur d'IA est injoignable."))


@pytest.fixture
def ai_enabled(settings):
    """Configuration minimale pour que l'endpoint réponde."""
    settings.AI_ENABLED = True
    settings.AI_PROVIDER = "fake"
    settings.AI_MEAL_SCAN_MODEL = "modele-de-test"
    return settings


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        username="autre", password="un-mot-de-passe-solide-1", status=UserStatus.ACTIVE
    )


@pytest.fixture
def chicken(db) -> Food:
    """Aliment Ciqual que la recherche doit trouver sur « poulet »."""
    food = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="1000",
        name="Poulet, cuisse, crue",
        reference_amount=Decimal("100"),
    )
    FoodNutrition.objects.create(
        food=food,
        energy_kcal=Decimal("120"),
        protein_g=Decimal("20"),
        carbohydrates_g=Decimal("0"),
        fat_g=Decimal("4"),
    )
    return food


@pytest.fixture
def apricot(db) -> Food:
    food = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="1001",
        name="Abricot, cru",
        reference_amount=Decimal("100"),
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("48"))
    return food


@pytest.fixture
def milk(db) -> Food:
    """Aliment mesuré en millilitres : les grammes n'y sont pas calculables."""
    food = Food.objects.create(
        source=FoodSource.CIQUAL,
        external_id="1002",
        name="Lait demi-écrémé",
        reference_amount=Decimal("100"),
        reference_unit="ml",
        default_unit_type="ml",
    )
    FoodNutrition.objects.create(food=food, energy_kcal=Decimal("46"))
    FoodPortion.objects.create(food=food, name="verre", milliliter_equivalent=Decimal("200"))
    return food


@pytest.fixture
def image_part() -> ImagePart:
    return ImagePart(media_type="image/jpeg", data=JPEG_BYTES)
