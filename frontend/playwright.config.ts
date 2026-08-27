import { defineConfig, devices } from '@playwright/test'

/**
 * Parcours de bout en bout.
 *
 * Playwright démarre lui-même le backend Django et un serveur statique servant
 * le build de production du frontend : le test s'exécute donc sur exactement
 * ce qui serait déployé.
 */

const BACKEND_PORT = process.env.E2E_BACKEND_PORT ?? '8011'
const FRONTEND_PORT = process.env.E2E_FRONTEND_PORT ?? '4173'
const PYTHON = process.env.E2E_PYTHON ?? '../backend/.venv/bin/python'

const backendEnv = {
  DJANGO_SETTINGS_MODULE: 'config.settings.local',
  DJANGO_SECRET_KEY: 'cle-de-test-e2e-sans-valeur-de-securite-0123456789',
  DJANGO_DEBUG: 'False',
  DJANGO_ALLOWED_HOSTS: 'localhost,127.0.0.1',
  // Le parcours utilise la base de développement et nettoie ses propres
  // comptes ; la CI la fournit vierge.
  DATABASE_URL: process.env.E2E_DATABASE_URL ?? 'postgres://mfp:mfp@localhost:5433/mfp',
  REDIS_URL: process.env.E2E_REDIS_URL ?? 'redis://localhost:6380/5',
  FRONTEND_URL: `http://localhost:${FRONTEND_PORT}`,
  BACKEND_URL: `http://localhost:${BACKEND_PORT}`,
  CORS_ALLOWED_ORIGINS: `http://localhost:${FRONTEND_PORT}`,
  CSRF_TRUSTED_ORIGINS: `http://localhost:${FRONTEND_PORT},http://localhost:${BACKEND_PORT}`,
  EMAIL_BACKEND: 'django.core.mail.backends.locmem.EmailBackend',
  // Meal Scan : fournisseur simulé, donc analyse déterministe et sans clé, et
  // exécution synchrone, donc sans worker Celery à démarrer.
  AI_ENABLED: 'True',
  AI_PROVIDER: 'fake',
  AI_MEAL_SCAN_MODEL: 'modele-simule',
  CELERY_TASK_ALWAYS_EAGER: 'True',
}

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  timeout: 60_000,

  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
    locale: 'fr-FR',
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  webServer: [
    {
      command: `${PYTHON} manage.py migrate --noinput && ${PYTHON} manage.py runserver ${BACKEND_PORT} --noreload`,
      cwd: '../backend',
      url: `http://localhost:${BACKEND_PORT}/health/`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: backendEnv,
    },
    {
      // Le build fige `VITE_API_BASE_URL` : il doit être refait avec l'URL du
      // backend E2E avant d'être servi.
      command: `npm run build && npm run preview -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { VITE_API_BASE_URL: `http://localhost:${BACKEND_PORT}/api/v1` },
    },
  ],
})
