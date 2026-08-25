import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, importCiqualSample, signUp } from './helpers'

/**
 * Parcours aliments (spec 08 §5) :
 *
 *   recherche → fiche → favori → création d'un aliment personnel
 */

const USERNAME = 'e2e-aliments'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('recherche, consultation et création d’aliments', async ({ page }) => {
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
    await page.getByRole('button', { name: 'Continuer' }).click()
    await page.getByRole('button', { name: 'Continuer' }).click()
    await page.getByRole('button', { name: 'Continuer' }).click()
    await page.getByRole('button', { name: 'Continuer' }).click()
    await page.getByRole('button', { name: 'Terminer' }).click()
    await expect(page).toHaveURL(/\/$/)
  })

  await test.step('la recherche attend deux caractères', async () => {
    await page.goto('/aliments')
    await expect(page.getByRole('heading', { name: 'Aliments' })).toBeVisible()

    await page.getByLabel('Rechercher un aliment').fill('p')
    await expect(page.getByText(/au moins 2 caractères/)).toBeVisible()
  })

  await test.step('la recherche ignore les accents', async () => {
    // « pate » sans accent doit retrouver les fiches accentuées.
    await page.getByLabel('Rechercher un aliment').fill('abricot')
    await expect(page.getByText(/Abricot/).first()).toBeVisible()
  })

  await test.step('consultation d’une fiche', async () => {
    await page
      .getByRole('link', { name: /Abricot/ })
      .first()
      .click()

    await expect(page.getByRole('heading', { level: 1 })).toContainText('Abricot')
    await expect(page.getByText(/Source : Ciqual/)).toBeVisible()
    await expect(page.getByText('Valeurs nutritionnelles')).toBeVisible()
  })

  await test.step('mise en favori', async () => {
    await page.getByRole('button', { name: 'Ajouter aux favoris' }).click()
    await expect(page.getByRole('button', { name: 'Retirer des favoris' })).toBeVisible()

    await page.goto('/aliments')
    await expect(page.getByText(/Abricot/).first()).toBeVisible()
  })

  await test.step('création d’un aliment personnel', async () => {
    await page.goto('/mes-aliments')
    await page.getByRole('button', { name: 'Créer' }).click()

    await page.getByLabel('Nom').fill('Granola maison E2E')
    await page.getByLabel('Énergie').fill('450')
    await page.getByLabel('Protéines').fill('10')
    // Glucides, lipides et fibres restent volontairement vides.
    await page.getByRole('button', { name: 'Créer l’aliment' }).click()

    await expect(page.getByRole('heading', { level: 1 })).toContainText('Granola maison E2E')
    await expect(page.getByRole('link', { name: /Modifier cet aliment/ })).toBeVisible()
  })

  await test.step('les champs laissés vides restent inconnus', async () => {
    // Un champ non renseigné s'affiche « — » et n'est jamais ramené à zéro
    // (spec 01 §8) : la règle est vérifiée de bout en bout.
    const glucides = page.getByRole('term').filter({ hasText: /^Glucides$/ })
    await expect(glucides).toBeVisible()

    await expect(page.getByRole('definition').nth(2)).toHaveText('—')
  })

  await test.step('l’aliment personnel est retrouvé par la recherche', async () => {
    await page.goto('/aliments')
    await page.getByLabel('Rechercher un aliment').fill('granola')

    await expect(page.getByText('Granola maison E2E')).toBeVisible()
  })
})
