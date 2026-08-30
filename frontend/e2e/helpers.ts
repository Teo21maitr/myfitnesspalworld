import { execFileSync } from 'node:child_process'

import type { Page } from '@playwright/test'

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

/** Importe l'extrait Ciqual versionné, pour que la recherche ait de la matière. */
export function importCiqualSample(): void {
  execFileSync(PYTHON, ['manage.py', 'import_ciqual', 'nutrition/tests/fixtures/ciqual'], {
    cwd: '../backend',
    env: backendEnv(),
    stdio: 'pipe',
  })
}

/** Dépose une demande d'inscription depuis l'interface. */
export async function signUp(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/demande-inscription')
  await page.getByLabel('Prénom').fill('Téo')
  await page.getByLabel('Nom', { exact: true }).fill('Maitrot')
  await page.getByLabel('Nom d’utilisateur').fill(username)
  await page.getByLabel('Mot de passe', { exact: true }).fill(password)
  await page.getByLabel('Confirmation du mot de passe').fill(password)
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click()
  await page.getByRole('heading', { name: 'Demande envoyée' }).waitFor()
}

const SEED_OFF_PRODUCT = [
  'from nutrition.models import Food, FoodNutrition, FoodSource, UnitType',
  'from django.utils import timezone',
  'food, _ = Food.objects.update_or_create(',
  '    source=FoodSource.OFF, external_id="3017620422003",',
  '    defaults={"name": "Nutella", "brand": "Ferrero", "barcode": "3017620422003",',
  '              "reference_amount": 100, "reference_unit": UnitType.GRAM,',
  '              "cache_refreshed_at": timezone.now(), "is_active": True})',
  'FoodNutrition.objects.update_or_create(food=food, defaults={"energy_kcal": "539"})',
].join('\n')

/**
 * Place un produit Open Food Facts dans le cache local.
 *
 * Le parcours doit être déterministe : en peuplant le cache, la résolution du
 * code-barres s'arrête avant tout appel réseau. Aucun test ne dépend ainsi de
 * la disponibilité ni du quota de la source.
 */
export function seedCachedOffProduct(): void {
  execFileSync(PYTHON, ['manage.py', 'shell', '-c', SEED_OFF_PRODUCT], {
    cwd: '../backend',
    env: backendEnv(),
    stdio: 'pipe',
  })
}

const CLEANUP_OFF = [
  'from nutrition.models import Food, FoodSource',
  'Food.objects.filter(source=FoodSource.OFF).delete()',
].join('; ')

export function cleanupOffProducts(): void {
  execFileSync(PYTHON, ['manage.py', 'shell', '-c', CLEANUP_OFF], {
    cwd: '../backend',
    env: backendEnv(),
    stdio: 'pipe',
  })
}

/**
 * Déclenche le balayage des rappels, comme le fait Celery beat.
 *
 * On passe par le service réel plutôt que par un raccourci de test : c'est le
 * même chemin qu'en production, contrainte d'unicité comprise.
 */
export function runDueReminders(): void {
  execFileSync(
    PYTHON,
    ['manage.py', 'shell', '-c', 'from notifications.services import reminders; reminders.run()'],
    { cwd: '../backend', env: backendEnv(), stdio: 'pipe' },
  )
}

/** Recule l'heure d'un rappel, pour qu'il devienne dû sans attendre. */
export function makeReminderDue(username: string): void {
  // Chaque entrée doit être une instruction complète : elles sont jointes par
  // `; `, et une expression coupée en trois deviendrait une erreur de syntaxe.
  const script = [
    'import os',
    'from datetime import timedelta',
    'from django.utils import timezone',
    'from accounts.models import normalize_username',
    'from notifications.models import Reminder',
    'moment = timezone.localtime() - timedelta(minutes=5)',
    'normalized = normalize_username(os.environ["E2E_USERNAME"])',
    'Reminder.objects.filter(user__normalized_username=normalized).update(time=moment.time())',
  ].join('; ')

  execFileSync(PYTHON, ['manage.py', 'shell', '-c', script], {
    cwd: '../backend',
    env: backendEnv({ E2E_USERNAME: username }),
    stdio: 'pipe',
  })
}
