"""Active les extensions PostgreSQL nécessaires à la recherche d'aliments.

`pg_trgm` fournit la recherche tolérante aux fautes et `unaccent` la
recherche insensible aux accents (spec 01 §7, spec 10 §4). Elles sont
installées dès le socle pour éviter d'avoir à réordonner les migrations
lorsque le modèle `Food` sera introduit.
"""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies: list = []

    operations = [
        TrigramExtension(),
        UnaccentExtension(),
    ]
