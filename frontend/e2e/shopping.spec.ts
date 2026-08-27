import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  importCiqualSample,
  signUp,
  resetThrottleCounters,
} from './helpers'

/**
 * Parcours liste de courses (spec 01 §16, spec 08 §5) :
 *
 *   composer une recette → générer les courses → régénérer dans la même liste
 *   et voir la quantité fusionner → cocher → ajouter un article à la main
 */

const USERNAME = 'e2e-courses'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  // Neuvième parcours : le quota de connexion de 10/min déborde sans remise à
  // zéro.
  resetThrottleCounters()
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('génération, regroupement et achat', async ({ page }) => {
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

  await test.step('une recette de 150 g d’abricot', async () => {
    await page.goto('/recettes/nouvelle')
    await page.getByLabel('Nom').fill('Compote express')
    await page.getByLabel('Portions').fill('2')
    await page.getByLabel('Chercher un ingrédient').fill('abricot')
    await page
      .getByRole('button', { name: /Abricot/ })
      .first()
      .click()
    await page.getByLabel('Quantité').fill('150')
    await page.getByRole('button', { name: /^Ajouter Abricot/ }).click()
    await page.getByRole('button', { name: 'Créer la recette' }).click()
    await expect(page).toHaveURL(/\/recettes\/\d+$/)
  })

  await test.step('générer les courses depuis cette recette', async () => {
    await page.goto('/courses')
    await expect(page.getByRole('heading', { name: 'Courses' })).toBeVisible()

    await page.getByLabel(/Compote express/).check()
    await page.getByRole('button', { name: 'Générer la liste' }).click()

    await expect(page).toHaveURL(/\/courses\/\d+$/)
    await expect(page.getByText(/Abricot/).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '150 g' })).toBeVisible()
  })

  await test.step('régénérer dans la même liste fusionne les quantités', async () => {
    // Le cœur de l'étape : 150 g + 150 g donnent une ligne à 300 g, pas deux
    // lignes ni une addition sans conversion.
    await page.goto('/courses')
    await page.getByLabel('Où ajouter').selectOption({ index: 1 })
    await page.getByLabel(/Compote express/).check()
    await page.getByRole('button', { name: 'Générer la liste' }).click()

    await expect(page).toHaveURL(/\/courses\/\d+$/)
    await expect(page.getByRole('button', { name: '300 g' })).toBeVisible()
    // Le contenu de la page, sans la barre de navigation.
    await expect(page.getByRole('main').getByRole('listitem')).toHaveCount(1)
  })

  await test.step('cocher un article le barre sans le déplacer', async () => {
    const checkbox = page.getByLabel(/Marquer .* comme acheté/).first()
    await checkbox.check()

    await expect(page.getByText(/à acheter/)).toContainText('0 article')
  })

  await test.step('ajouter un article à la main', async () => {
    await page.getByLabel('Article').fill('Sel')
    await page
      .locator('form')
      .filter({ has: page.getByLabel('Article') })
      .getByRole('button', { name: 'Ajouter' })
      .click()

    await expect(page.getByText('Sel')).toBeVisible()
  })
})
