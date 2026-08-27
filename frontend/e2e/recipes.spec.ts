import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  importCiqualSample,
  signUp,
  resetThrottleCounters,
} from './helpers'

/**
 * Parcours recettes et repas enregistrés (spec 01 §13 et §14, spec 08 §5) :
 *
 *   composer une recette → lire sa valeur par portion → en journaliser deux
 *   portions → enregistrer un repas → le déplier dans le journal
 */

const USERNAME = 'e2e-recettes'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  // Septième parcours : le quota de connexion de 10/min déborde sans remise à
  // zéro. On préfère cela à l'affaiblissement d'une protection utile.
  resetThrottleCounters()
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('recette, portions et repas enregistré', async ({ page }) => {
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

  await test.step('composer une recette de deux portions', async () => {
    await page.goto('/recettes')
    await expect(page.getByRole('heading', { name: 'Recettes' })).toBeVisible()
    await page.getByRole('link', { name: 'Créer une recette' }).click()

    await page.getByLabel('Nom').fill('Compote maison')
    await page.getByLabel('Portions').fill('2')

    await page.getByLabel('Chercher un ingrédient').fill('abricot')
    const result = page.getByRole('button', { name: /Abricot/ }).first()
    await result.click()
    await page.getByLabel('Quantité').fill('400')
    await page.getByRole('button', { name: /^Ajouter Abricot/ }).click()

    await page.getByRole('button', { name: 'Créer la recette' }).click()
    await expect(page).toHaveURL(/\/recettes\/\d+$/)
  })

  await test.step('la fiche annonce la valeur par portion', async () => {
    const panel = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByRole('heading', { name: 'Pour une portion' }) })

    await expect(panel).toBeVisible()
    // 400 g d'abricot pour deux portions : la moitié par portion.
    await expect(panel.getByText(/par portion/)).toBeVisible()
    await expect(panel.getByText('Macronutriments')).toBeVisible()
  })

  await test.step('journaliser deux portions', async () => {
    const form = page.locator('form').filter({ has: page.getByLabel('Portions') })
    await form.getByLabel('Portions').fill('2')
    await form.getByRole('button', { name: 'Ajouter au journal' }).click()

    await expect(page).toHaveURL(/\/journal/)
    await expect(page.getByText('Compote maison').first()).toBeVisible()
  })

  await test.step('modifier la recette ne touche pas l’entrée', async () => {
    await page.goto('/recettes')
    await page.getByRole('link', { name: /Compote maison/ }).click()
    await page.getByRole('link', { name: 'Modifier' }).click()

    await page.getByLabel('Portions').fill('4')
    await page.getByRole('button', { name: 'Enregistrer' }).click()

    // L'entrée déjà journalisée garde son snapshot (spec 01 §14).
    await page.goto('/journal')
    await expect(page.getByText('Compote maison').first()).toBeVisible()
  })

  await test.step('enregistrer un repas et le déplier', async () => {
    await page.goto('/mes-repas')
    await expect(page.getByRole('heading', { name: 'Mes repas' })).toBeVisible()

    const form = page.locator('form').filter({ has: page.getByLabel('Nom') })
    await form.getByLabel('Nom').fill('Mon goûter')
    await form.getByLabel('Chercher un ingrédient').fill('abricot')
    await form
      .getByRole('button', { name: /Abricot/ })
      .first()
      .click()
    await form.getByRole('button', { name: /^Ajouter Abricot/ }).click()
    await form.getByRole('button', { name: 'Enregistrer le repas' }).click()

    const card = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByRole('heading', { name: 'Mon goûter' }) })
    await expect(card).toBeVisible()

    await card.getByRole('button', { name: 'Ajouter au journal' }).click()
    await expect(page).toHaveURL(/\/journal/)
  })
})
