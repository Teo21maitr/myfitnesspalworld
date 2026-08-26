import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  importCiqualSample,
  signUp,
  resetThrottleCounters,
} from './helpers'

/**
 * Parcours accueil et copie (spec 01 §5 et §23, spec 08 §5) :
 *
 *   journaliser → voir le bilan sur l'accueil → copier la journée vers demain
 *   → déplacer une entrée d'un repas à l'autre
 */

const USERNAME = 'e2e-accueil'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  // Le quota de connexion est volontairement serré (10/min). Chaque
  // parcours crée un compte et s'y connecte : à cinq parcours, le compteur
  // déborde. On le remet à zéro plutôt que d'affaiblir la protection.
  resetThrottleCounters()
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('tableau de bord, copie de journée et déplacement', async ({ page }) => {
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

  await test.step('l’accueil affiche le bilan du jour', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Aujourd’hui' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Calories' })).toBeVisible()

    // L'onboarding a enregistré une pesée : le widget poids n'est pas vide.
    await expect(page.getByRole('heading', { name: 'Poids' })).toBeVisible()
  })

  await test.step('un aliment journalisé apparaît dans le bilan', async () => {
    await page.goto('/aliments')
    await page.getByLabel('Rechercher un aliment').fill('abricot')
    await page
      .getByRole('link', { name: /Abricot/ })
      .first()
      .click()
    await page.getByLabel('Quantité').fill('200')
    await page.getByRole('button', { name: 'Ajouter au journal' }).click()
    await expect(page).toHaveURL(/\/journal/)

    await page.goto('/')
    const calories = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByRole('heading', { name: 'Calories' }) })
    await expect(calories.getByText(/restantes/)).toBeVisible()
  })

  await test.step('la journée se copie vers demain', async () => {
    await page.goto('/journal')
    await page.getByRole('button', { name: /Copier la journée/ }).click()

    const panel = page.locator('[data-slot="card"]').filter({ hasText: 'Copier cette journée' })
    await panel.getByRole('button', { name: 'Ajouter', exact: true }).click()
    await panel.getByRole('button', { name: 'Copier', exact: true }).click()

    // Le lendemain porte désormais la même entrée.
    await page.getByRole('button', { name: 'Jour suivant' }).click()
    await expect(page.getByRole('link', { name: /Abricot/ }).first()).toBeVisible()
  })

  await test.step('une entrée se déplace vers un autre repas', async () => {
    await page
      .getByRole('button', { name: /^Déplacer / })
      .first()
      .click()
    await page.getByRole('button', { name: 'Dîner', exact: true }).click()

    const dinner = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByRole('heading', { name: 'Dîner', exact: true }) })
    await expect(dinner.getByRole('link', { name: /Abricot/ })).toBeVisible()
  })
})
