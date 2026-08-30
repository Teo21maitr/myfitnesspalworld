/**
 * Déclaration du projet Railway (spec 09).
 *
 * Remplace les `railway.json`, que Railway a dépréciés et refuse désormais de
 * déployer. Le nouveau format décrit **tous les services dans un seul fichier**,
 * ce qui résout au passage le problème que les trois fichiers contournaient :
 * les trois services backend partagent la racine `/backend`, et un fichier
 * unique par racine leur imposait la même commande et le même healthcheck.
 *
 * Les variables restent en `preserve()` : elles vivent dans Railway, et aucun
 * secret n'entre dans ce dépôt (CLAUDE.md §2).
 */
import { defineRailway, github, postgres, preserve, project, redis, service, volume } from 'railway/iac'

/** Variables communes aux trois services backend, gérées côté Railway. */
const backendEnv = {
  BACKEND_URL: preserve(),
  CELERY_BROKER_URL: preserve(),
  CELERY_RESULT_BACKEND: preserve(),
  CORS_ALLOWED_ORIGINS: preserve(),
  CSRF_TRUSTED_ORIGINS: preserve(),
  DATABASE_URL: preserve(),
  DEFAULT_FROM_EMAIL: preserve(),
  DJANGO_ALLOWED_HOSTS: preserve(),
  DJANGO_SECRET_KEY: preserve(),
  DJANGO_SETTINGS_MODULE: preserve(),
  EMAIL_BACKEND: preserve(),
  EMAIL_HOST: preserve(),
  EMAIL_HOST_PASSWORD: preserve(),
  EMAIL_HOST_USER: preserve(),
  EMAIL_PORT: preserve(),
  EMAIL_USE_TLS: preserve(),
  FRONTEND_URL: preserve(),
  OFF_CONTACT_EMAIL: preserve(),
  REDIS_URL: preserve(),
}

export default defineRailway(() => {
  const backendSource = github('Teo21maitr/myfitnesspalworld', {
    checkSuites: false,
    rootDirectory: '/backend',
  })

  const Redis = redis('Redis', { region: 'us-west2' })
  Redis.deploy = {
    startCommand:
      '/bin/sh -c "rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH"',
  }
  const Postgres = postgres('Postgres', { region: 'us-west2' })

  const postgresVolume = volume('postgres-volume', {
    alerts: { usage: { '100': {}, '80': {}, '95': {} } },
    allowOnlineResize: true,
    region: 'us-west2',
    sizeMB: 5000,
  })
  const redisVolume = volume('redis-volume', {
    alerts: { usage: { '100': {}, '80': {}, '95': {} } },
    allowOnlineResize: true,
    region: 'us-west2',
    sizeMB: 5000,
  })

  const Backend = service('Backend', {
    source: backendSource,
    replicas: { 'us-west2': 1 },
    networking: { privateNetworkEndpoint: 'myfitnesspalworld' },
    // `$PORT` est imposé par la plateforme ; l'image accepte les deux.
    start:
      'gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 60 --access-logfile - --error-logfile -',
    // Les migrations passent avant que la nouvelle version ne serve.
    preDeploy: 'python manage.py migrate --noinput',
    // Vérifie la base **et** le cache : un service dégradé répond 503.
    healthcheck: '/health/',
    healthcheckTimeout: 60,
    env: backendEnv,
  })

  // Worker et beat n'écoutent sur aucun port : ni domaine, ni healthcheck HTTP.
  // C'est précisément ce qu'un fichier partagé leur imposait à tort.
  const celeryWorker = service('celery-worker', {
    source: backendSource,
    replicas: { 'us-west2': 1 },
    start: 'celery -A config worker -l info',
    env: backendEnv,
  })

  // Un seul exemplaire : deux ordonnanceurs enverraient chaque rappel deux
  // fois. L'unicité en base l'empêcherait, mais autant ne pas la solliciter.
  const celeryBeat = service('celery-beat', {
    source: backendSource,
    replicas: { 'us-west2': 1 },
    start: 'celery -A config beat -l info --schedule /tmp/celerybeat-schedule',
    env: backendEnv,
  })

  return project('intelligent-adaptation', {
    resources: [Backend, celeryWorker, celeryBeat, Redis, Postgres, postgresVolume, redisVolume],
  })
})
