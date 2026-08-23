"""Projet Django MyFitnessPalworld.

L'application Celery est importée ici pour que `@shared_task` fonctionne dès
le chargement de Django.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
