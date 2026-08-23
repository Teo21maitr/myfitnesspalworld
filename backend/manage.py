#!/usr/bin/env python
"""Utilitaire de ligne de commande Django."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - garde-fou d'environnement
        raise ImportError(
            "Django est introuvable. L'environnement virtuel est-il activé "
            "et les dépendances installées ?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
