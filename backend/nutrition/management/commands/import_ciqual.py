"""Importe la table Ciqual dans le référentiel d'aliments (spec 11 §2).

    python manage.py import_ciqual <dossier-ou-archive>

L'import est idempotent : il identifie chaque aliment par son code Ciqual et
met à jour les fiches existantes au lieu de les dupliquer. Le jeu de données
n'est pas versionné dans le dépôt — voir le README pour le récupérer.
"""

import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nutrition.models import Food, FoodNutrition, FoodSource, UnitType
from nutrition.services.ciqual import (
    CIQUAL_ATTRIBUTION,
    CIQUAL_VERSION,
    CiqualFood,
    extract_archive,
    read_foods,
)

NUTRITION_FIELDS = [
    field.name for field in FoodNutrition._meta.fields if field.name not in {"id", "food"}
]


class Command(BaseCommand):
    help = "Importe la table de composition nutritionnelle Ciqual."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "source",
            help="Dossier contenant les fichiers XML Ciqual, ou archive ZIP.",
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=None,
            help="N'importer que les N premiers aliments, pour le développement.",
        )

    def handle(self, *args, **options) -> None:
        source = Path(options["source"]).expanduser()
        if not source.exists():
            raise CommandError(f"Chemin introuvable : {source}")

        with tempfile.TemporaryDirectory() as workspace:
            directory = extract_archive(source, Path(workspace)) if source.is_file() else source

            self.stdout.write(f"Lecture de {directory}…")
            try:
                foods = read_foods(directory)
            except FileNotFoundError as exc:
                raise CommandError(str(exc)) from exc

        if options["sample"]:
            foods = dict(list(foods.items())[: options["sample"]])

        self.stdout.write(f"{len(foods)} aliments lus, écriture en base…")
        created, updated, unknown_values = self._write(foods)

        self.stdout.write(
            self.style.SUCCESS(
                f"Import terminé : {created} créé(s), {updated} mis à jour. "
                f"{unknown_values} teneur(s) inconnue(s) laissée(s) nulles."
            )
        )
        self.stdout.write(f"Source : {CIQUAL_ATTRIBUTION} (version {CIQUAL_VERSION}).")

    @transaction.atomic
    def _write(self, foods: dict[str, CiqualFood]) -> tuple[int, int, int]:
        """Écrit les aliments et leur composition en une seule transaction."""
        existing = {
            food.external_id: food
            for food in Food.objects.filter(
                source=FoodSource.CIQUAL, external_id__in=foods.keys()
            ).select_related("nutrition")
        }

        created = updated = 0
        unknown_values = 0

        for code, parsed in foods.items():
            food = existing.get(code)

            if food is None:
                food = Food(source=FoodSource.CIQUAL, external_id=code)
                created += 1
            else:
                updated += 1

            food.name = parsed.name
            # Les fiches Ciqual sont officielles et immuables côté utilisateur.
            food.is_verified = True
            food.is_active = True
            food.deleted_at = None
            food.default_unit_type = UnitType.GRAM
            food.reference_unit = UnitType.GRAM
            food.reference_amount = 100
            food.save()

            values = dict(parsed.nutrients)
            values["vitamin_a_ug"] = parsed.vitamin_a_ug()
            unknown_values += sum(1 for name in NUTRITION_FIELDS if values.get(name) is None)

            FoodNutrition.objects.update_or_create(
                food=food,
                defaults={name: values.get(name) for name in NUTRITION_FIELDS},
            )

        return created, updated, unknown_values
