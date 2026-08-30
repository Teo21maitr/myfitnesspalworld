# Image backend, en trois étages.
#
# `dev` sert au développement local (docker compose) ; `production` part sur la
# plateforme. La séparation n'est pas cosmétique : sans elle, pytest et ruff
# voyageraient jusqu'en production.
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# `psycopg[binary]` embarque libpq : aucune dépendance de compilation requise.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Développement : outils de test et de lint en plus.
# -----------------------------------------------------------------------------
FROM base AS dev

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

# -----------------------------------------------------------------------------
# Production
# -----------------------------------------------------------------------------
FROM base AS production

# Le sens sûr de l'erreur : une variable oubliée sur la plateforme donne la
# production, jamais le développement — où `DEBUG` vaut True et les cookies ne
# sont pas `Secure`. `docker-compose.yml` surcharge déjà cette valeur.
ENV DJANGO_SETTINGS_MODULE=config.settings.production

COPY . .

# `collectstatic` **à la construction**, pour que le manifeste voyage dans
# l'image. Confié à un pré-déploiement, il s'oublie — et son absence ne se voit
# qu'à l'ouverture de la première page d'admin, en production.
#
# Les valeurs ci-dessous sont jetables : `production.py` exige ces variables
# pour s'importer, et la construction n'a pas à connaître les vraies.
RUN DJANGO_SECRET_KEY=construction-uniquement-sans-valeur-de-securite \
    DJANGO_ALLOWED_HOSTS=localhost \
    CORS_ALLOWED_ORIGINS=https://localhost \
    CSRF_TRUSTED_ORIGINS=https://localhost \
    FRONTEND_URL=https://localhost \
    BACKEND_URL=https://localhost \
    DEFAULT_FROM_EMAIL=build@localhost \
    EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend \
    python manage.py collectstatic --noinput --clear

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# `$PORT` est imposé par la plateforme (spec 09 §8) ; 8000 sert en local.
# `--access-logfile -` envoie les journaux sur la sortie standard, seul endroit
# où la plateforme les lit.
CMD ["sh", "-c", "gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-60} \
    --access-logfile - \
    --error-logfile -"]
