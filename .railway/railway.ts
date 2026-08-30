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

/**
 * Réglages définis dans les *Shared Variables* du projet.
 *
 * Railway ne les injecte **pas** automatiquement : chaque service doit les
 * référencer. Les déclarer ici plutôt que de cliquer service par service évite
 * l'oubli qui a coûté un déploiement — un service privé de
 * `CELERY_BROKER_URL` ne s'arrête pas, il retombe sur le broker par défaut de
 * Celery et cherche RabbitMQ sur `127.0.0.1` indéfiniment.
 */
const SHARED = [
  'BACKEND_URL',
  'CORS_ALLOWED_ORIGINS',
  'CSRF_TRUSTED_ORIGINS',
  'DEFAULT_FROM_EMAIL',
  'DJANGO_ALLOWED_HOSTS',
  'DJANGO_SECRET_KEY',
  'DJANGO_SETTINGS_MODULE',
  'EMAIL_BACKEND',
  'FRONTEND_URL',
  'OFF_CONTACT_EMAIL',
  // Les trois services backend en ont besoin : le garde-fou de démarrage
  // refuse un backend d'API sans sa clé, et le worker envoie autant d'emails
  // que la vue qui l'appelle. Les réglages SMTP, eux, ont disparu — la
  // plateforme ferme ces ports, l'envoi passe par une API HTTP.
  'RESEND_API_KEY',
] as const

export default defineRailway((ctx) => {
  // `checkSuites` : attendre les vérifications GitHub avant de déployer `main`
  // (spec 08 §6). Sans cela, un push rouge part en production.
  const backendSource = github('Teo21maitr/myfitnesspalworld', {
    checkSuites: true,
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

  /**
   * Ce que reçoit chaque service backend.
   *
   * Les quatre chaînes de connexion sont des **références aux bases**, pas des
   * valeurs recopiées : elles suivent une rotation d'identifiants toutes
   * seules. Les secrets, eux, restent dans les Shared Variables — ce fichier
   * les nomme sans jamais les contenir.
   */
  const backendEnv = {
    ...Object.fromEntries(SHARED.map((name) => [name, ctx.shared[name]])),
    DATABASE_URL: Postgres.env.DATABASE_URL,
    REDIS_URL: Redis.env.REDIS_URL,
    CELERY_BROKER_URL: Redis.env.REDIS_URL,
    CELERY_RESULT_BACKEND: Redis.env.REDIS_URL,
  }

  const Backend = service('Backend', {
    source: backendSource,
    replicas: { 'us-west2': 1 },
    networking: { privateNetworkEndpoint: 'myfitnesspalworld' },
    // Aucune commande de démarrage ici : c'est le `CMD` de l'image qui sert.
    //
    // Railway exécute la commande déclarée **sans shell**. Une commande écrite
    // ici avec `--bind 0.0.0.0:$PORT` passe les cinq caractères `$PORT` à
    // gunicorn tel quel, qui refuse de démarrer — la conteneur redémarre en
    // boucle et le healthcheck échoue, sans que rien ne nomme la variable.
    // Le `CMD` du Dockerfile, lui, passe par `sh -c` et développe `${PORT:-8000}`.
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

  /**
   * Le frontend. `VITE_API_BASE_URL` est figée **dans le bundle** au moment de
   * la construction : la changer ici impose de reconstruire, pas seulement de
   * redémarrer. Elle reste en `preserve()` pour que ce fichier ne l'écrase pas.
   */
  const frontend = service('myfitnesspalworld', {
    source: github('Teo21maitr/myfitnesspalworld', {
      checkSuites: true,
      rootDirectory: '/frontend',
    }),
    replicas: { 'us-west2': 1 },
    networking: { privateNetworkEndpoint: 'myfitnesspalworld-2253' },
    env: {
      VITE_API_BASE_URL: preserve(),
      // Cible du relais `/api/`, qui met l'API sous la même origine que
      // l'application. Déclarée ici pour qu'un `apply` ne la supprime pas :
      // sans elle, nginx ne démarre pas.
      BACKEND_ORIGIN: preserve(),
    },
  })

  return project('intelligent-adaptation', {
    resources: [
      Backend,
      celeryWorker,
      celeryBeat,
      frontend,
      Redis,
      Postgres,
      postgresVolume,
      redisVolume,
    ],
  })
})
