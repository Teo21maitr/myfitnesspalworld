import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, signUp, resetThrottleCounters } from './helpers'

/**
 * Parcours progression (spec 01 §19, spec 08 §5) :
 *
 *   se peser → corriger la pesée du jour → ajouter une pesée antérieure
 *   → lire la courbe → relever une mensuration
 */

const USERNAME = 'e2e-progression'
const PASSWORD = 'un-mot-de-passe-e2e-1'

/** Date passée, au format attendu par un champ `type="date"`. */
function daysAgo(days: number): string {
  const value = new Date()
  value.setDate(value.getDate() - days)
  return value.toISOString().slice(0, 10)
}

test.beforeAll(() => {
  // Le quota de connexion est volontairement serré (10/min) : à six parcours,
  // le compteur déborde. On le remet à zéro plutôt que d'affaiblir la
  // protection.
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('pesées, courbe et mensurations', async ({ page }) => {
  await test.step('création du compte et onboarding', async () => {
    await signUp(page, USERNAME, PASSWORD)
    acceptRegistrationRequest(USERNAME)

    await page.goto('/connexion')
    await page.getByLabel('Nom d’utilisateur').fill(USERNAME)
    await page.getByLabel('Mot de passe').fill(PASSWORD)
    await page.getByRole('button', { name: 'Se connecter' }).click()

    await expect(page).toHaveURL(/\/onboarding$/)
    await page.getByLabel('Date de naissance').fill('1996-01-01')
    await page.getByLabel('Sexe utilisé pour le calcul').selectOption('MALE')
    await page.getByLabel('Taille').fill('180')
    await page.getByLabel('Poids actuel').fill('80')
    await page.getByRole('button', { name: 'Continuer' }).click()
    await page.getByRole('radio', { name: /Maintenir mon poids/ }).check()
    await page.getByRole('button', { name: 'Continuer' }).click()
    await page.getByRole('radio', { name: /Sédentaire/ }).check()
    for (let index = 0; index < 4; index += 1) {
      await page.getByRole('button', { name: 'Continuer' }).click()
    }
    await page.getByRole('button', { name: 'Terminer' }).click()
    await page.waitForURL((url) => !url.pathname.includes('onboarding'))
  })

  // La page porte deux formulaires ; chacun a son bouton d'enregistrement.
  const weightForm = page.locator('form').filter({ has: page.getByLabel('Poids (kg)') })
  const measurementForm = page
    .locator('form')
    .filter({ has: page.getByLabel('Tour de taille (cm)') })
  const history = page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByRole('heading', { name: 'Historique des pesées' }) })

  await test.step('la pesée de l’onboarding est déjà là', async () => {
    await page.goto('/progression')
    await expect(page.getByRole('heading', { name: 'Progression' })).toBeVisible()

    await expect(history.getByRole('listitem')).toHaveCount(1)
    await expect(history).toContainText('80')

    // La date du jour porte déjà une pesée : le formulaire l'annonce avant
    // l'envoi plutôt que de laisser croire à un doublon.
    await expect(weightForm.getByRole('button', { name: 'Mettre à jour' })).toBeVisible()
  })

  await test.step('corriger la pesée du jour ne crée pas de doublon', async () => {
    await weightForm.getByLabel('Poids (kg)').fill('79')
    await weightForm.getByRole('button', { name: 'Mettre à jour' }).click()

    await expect(history).toContainText('79')
    await expect(history.getByRole('listitem')).toHaveCount(1)
  })

  await test.step('une pesée antérieure complète l’historique', async () => {
    await weightForm.getByLabel('Date').fill(daysAgo(10))
    await weightForm.getByLabel('Poids (kg)').fill('82')
    await weightForm.getByRole('button', { name: 'Enregistrer' }).click()

    await expect(history.getByRole('listitem')).toHaveCount(2)
  })

  await test.step('la courbe reprend les deux mesures', async () => {
    await expect(page.getByRole('img', { name: /Poids du .*2 mesures/ })).toBeVisible()
  })

  await test.step('une mensuration se relève et s’affiche', async () => {
    await measurementForm.getByLabel('Tour de taille (cm)').fill('85')
    await measurementForm.getByRole('button', { name: 'Enregistrer' }).click()

    const measurements = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByRole('heading', { name: 'Mensurations' }) })
    await expect(measurements.getByRole('listitem')).toHaveCount(1)
    await expect(measurements).toContainText('Tour de taille')
  })

  await test.step('l’accueil reprend le poids corrigé', async () => {
    await page.goto('/')
    const weight = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByRole('heading', { name: 'Poids' }) })
    await expect(weight).toContainText('79')
  })
})
