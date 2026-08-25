import { execFileSync } from 'node:child_process'

const PYTHON = process.env.E2E_PYTHON ?? '../backend/.venv/bin/python'

function backendEnv(extra: Record<string, string> = {}): NodeJS.ProcessEnv {
  return {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'config.settings.local',
    DJANGO_SECRET_KEY: 'cle-de-test-e2e-sans-valeur-de-securite-0123456789',
    DATABASE_URL: process.env.E2E_DATABASE_URL ?? 'postgres://mfp:mfp@localhost:5433/mfp',
    REDIS_URL: process.env.E2E_REDIS_URL ?? 'redis://localhost:6380/5',
    EMAIL_BACKEND: 'django.core.mail.backends.locmem.EmailBackend',
    ...extra,
  }
}

/**
 * Joue la validation administrateur.
 *
 * On passe par la commande de gestion réelle plutôt que par un endpoint de
 * fixture : aucune route de test n'est ainsi exposée par l'application.
 */
export function acceptRegistrationRequest(username: string): void {
  execFileSync(PYTHON, ['manage.py', 'accept_registration_request', username], {
    cwd: '../backend',
    env: backendEnv(),
    stdio: 'pipe',
  })
}

const CLEANUP_SCRIPT = [
  'import os',
  'from accounts.models import RegistrationRequest, User, normalize_username',
  'normalized = normalize_username(os.environ["E2E_USERNAME"])',
  'User.objects.filter(normalized_username=normalized).delete()',
  'RegistrationRequest.objects.filter(normalized_username=normalized).delete()',
].join('; ')

/** Retire d'éventuels restes d'une exécution précédente. */
export function cleanupUser(username: string): void {
  execFileSync(PYTHON, ['manage.py', 'shell', '-c', CLEANUP_SCRIPT], {
    cwd: '../backend',
    env: backendEnv({ E2E_USERNAME: username }),
    stdio: 'pipe',
  })
}

/** Vide le cache utilisé par le throttling DRF (base Redis dédiée à l'E2E). */
export function resetThrottleCounters(): void {
  execFileSync(
    PYTHON,
    ['manage.py', 'shell', '-c', 'from django.core.cache import cache; cache.clear()'],
    {
      cwd: '../backend',
      env: backendEnv(),
      stdio: 'pipe',
    },
  )
}
