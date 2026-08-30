"""Importe la table Ciqual dans le référentiel d'aliments (spec 11 §2).

    python manage.py import_ciqual <dossier-ou-archive-ou-url>

L'import est idempotent : il identifie chaque aliment par son code Ciqual et
met à jour les fiches existantes au lieu de les dupliquer. Le jeu de données
n'est pas versionné dans le dépôt — voir le README pour le récupérer.

Une URL est acceptée parce que l'import doit pouvoir tourner **dans le
conteneur de production**, où il n'y a ni fichier déposé ni outil pour en
transférer un. Le conteneur va chercher l'archive lui-même, l'extrait dans un
dossier temporaire, et ne laisse rien derrière lui.
"""

import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nutrition.models import Food, FoodNutrition, FoodSource, UnitType
from nutrition.services.ciqual import (
    CiqualFood,
    attribution,
    extract_archive,
    read_foods,
    read_version,
)

#: Taille au-delà de laquelle on refuse de télécharger. L'archive officielle
#: pèse moins de deux mégaoctets ; cent est déjà large. La borne existe pour
#: qu'une URL erronée échoue vite plutôt que de remplir le disque du conteneur.
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024

NUTRITION_FIELDS = [
    field.name for field in FoodNutrition._meta.fields if field.name not in {"id", "food"}
]


class Command(BaseCommand):
    help = "Importe la table de composition nutritionnelle Ciqual."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "source",
            help=(
                "Dossier contenant les fichiers XML Ciqual, archive 7z ou ZIP, "
                "ou URL https de l'archive publiée par l'Anses."
            ),
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=None,
            help="N'importer que les N premiers aliments, pour le développement.",
        )

    def handle(self, *args, **options) -> None:
        raw = options["source"]

        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)

            if urlparse(raw).scheme in {"http", "https"}:
                source = self._download(raw, root)
            else:
                source = Path(raw).expanduser()
                if not source.exists():
                    raise CommandError(f"Chemin introuvable : {source}")

            directory = extract_archive(source, root / "extrait") if source.is_file() else source

            self.stdout.write(f"Lecture de {directory}…")
            try:
                foods = read_foods(directory)
                version = read_version(directory)
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
        self.stdout.write(f"Source : {attribution(version)} (version {version}).")

    def _download(self, url: str, destination: Path) -> Path:
        """Rapatrie l'archive publiée, sans jamais rien laisser sur le disque.

        `https` est exigé : l'archive sert de référentiel nutritionnel à toute
        l'application, et un intermédiaire pourrait en modifier le contenu sur
        une liaison en clair.
        """
        if urlparse(url).scheme != "https":
            raise CommandError("Seules les URL https sont acceptées.")

        target = destination / (Path(urlparse(url).path).name or "ciqual.7z")
        self.stdout.write(f"Téléchargement de {url}…")

        try:
            with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_DOWNLOAD_BYTES:
                    raise CommandError(f"Archive trop volumineuse : {declared} octets.")

                written = 0
                with target.open("wb") as handle:
                    while chunk := response.read(1024 * 256):
                        written += len(chunk)
                        if written > MAX_DOWNLOAD_BYTES:
                            raise CommandError("Archive trop volumineuse.")
                        handle.write(chunk)
        except OSError as exc:
            raise CommandError(f"Téléchargement impossible : {exc}") from exc

        self.stdout.write(f"{written / 1024 / 1024:.1f} Mo téléchargés.")
        return target

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
