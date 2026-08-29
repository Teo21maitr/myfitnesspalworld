import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  importCiqualSample,
  resetThrottleCounters,
  signUp,
} from './helpers'

/**
 * Parcours planification (spec 01 §15, spec 08 §5) :
 *
 *   composer → relire → enregistrer → journaliser → liste de courses
 *
 * La proposition n'est jamais persistée : ce parcours vérifie qu'aucun
 * planning n'existe avant validation, et que l'ajout au journal ne remplace
 * rien.
 */

const USERNAME = 'e2e-planner'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  resetThrottleCounters()
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('composition d’une planification, journal et courses', async ({ page }) => {
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

  await test.step('composer deux journées', async () => {
    await page.goto('/planification')
    await expect(page.getByRole('heading', { name: 'Planification', exact: true })).toBeVisible()

    await page.getByLabel('Nombre de jours').fill('2')
    await page.getByRole('button', { name: 'Composer le plan' }).click()

    await expect(page.getByText('Proposition')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText('Jour 1 sur 2')).toBeVisible()
  })

  await test.step('la proposition n’est pas encore un planning', async () => {
    // Elle vit dans la tâche, pas en base : « Mes plannings » reste vide.
    await expect(page.getByText('Aucune planification pour le moment.')).toBeVisible()
  })

  await test.step('enregistrer, puis journaliser', async () => {
    await page.getByRole('button', { name: 'Enregistrer cette planification' }).click()
    await expect(page).toHaveURL(/\/planification\/\d+$/)

    await page.getByRole('button', { name: 'Ajouter au journal' }).click()
    await expect(page).toHaveURL(/\/journal$/)
    await expect(page.getByRole('main')).toContainText(/Poulet|Abricot/i)
  })

  await test.step('en tirer la liste de courses', async () => {
    await page.goBack()
    await page.getByRole('button', { name: 'Liste de courses' }).click()

    await expect(page).toHaveURL(/\/courses\/\d+$/)
    await expect(page.getByRole('main')).toContainText(/Poulet|Abricot/i)
  })
})
