"""Application Celery.

Le nom du module est `config`, ce qui rend valides les commandes de
déploiement `celery -A config worker` et `celery -A config beat` (spec 09).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
