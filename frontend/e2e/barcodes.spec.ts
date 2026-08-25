import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupOffProducts,
  cleanupUser,
  seedCachedOffProduct,
  signUp,
} from './helpers'

/**
 * Parcours code-barres (spec 01 §10, spec 08 §5) :
 *
 *   saisie d'un code → fiche produit
 *   code inconnu → création préremplie
 *
 * Aucun appel n'est fait à Open Food Facts. Le produit connu est placé dans le
 * cache local avant le test, et le cas « inconnu » est simulé au niveau du
 * navigateur : un parcours ne doit dépendre ni du réseau ni d'un quota partagé.
 */

const USERNAME = 'e2e-codebarres'
const PASSWORD = 'un-mot-de-passe-e2e-1'
const KNOWN_BARCODE = '3017620422003'
const UNKNOWN_BARCODE = '9999999999999'

test.beforeAll(() => {
  cleanupUser(USERNAME)
  cleanupOffProducts()
  seedCachedOffProduct()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
  cleanupOffProducts()
})

test('résolution d’un code-barres et création d’un produit inconnu', async ({ page }) => {
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

  await test.step('un code connu ouvre la fiche du produit', async () => {
    await page.goto('/scanner')
    await expect(page.getByRole('heading', { name: 'Scanner un produit' })).toBeVisible()

    // La saisie manuelle est toujours disponible : elle ne dépend ni de la
    // caméra ni de son autorisation (spec 06 §6).
    await page.getByLabel('Code-barres').fill(KNOWN_BARCODE)
    await page.getByRole('button', { name: /Chercher ce produit/ }).click()

    await expect(page).toHaveURL(/\/aliments\/\d+$/)
    await expect(page.getByRole('heading', { name: 'Nutella' })).toBeVisible()
    await expect(page.getByText('Open Food Facts').first()).toBeVisible()
  })

  await test.step('un code inconnu mène au formulaire prérempli', async () => {
    // Le backend interrogerait Open Food Facts : on répond à sa place pour
    // rester hors réseau, comme l'autorise la spec 08 §5.
    await page.route('**/api/v1/barcodes/**', (route) =>
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'product_not_found',
          message: 'Ce produit est introuvable. Vous pouvez le créer vous-même.',
          errors: {},
        }),
      }),
    )

    await page.goto('/scanner')
    await page.getByLabel('Code-barres').fill(UNKNOWN_BARCODE)
    await page.getByRole('button', { name: /Chercher ce produit/ }).click()

    await page.getByRole('link', { name: 'Créer ce produit' }).click()

    // Le code est repris tel quel : il n'a pas à être recopié depuis
    // l'emballage (spec 01 §10).
    await expect(page.getByLabel('Code-barres (facultatif)')).toHaveValue(UNKNOWN_BARCODE)
  })
})
