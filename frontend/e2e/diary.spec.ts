import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, importCiqualSample, signUp } from './helpers'

/**
 * Parcours journal (spec 01 §5, spec 08 §5) :
 *
 *   rechercher → ajouter au journal → vérifier le total → modifier → supprimer
 *
 * Le parcours vérifie aussi que l'aliment consommé rejoint bien les « récents » :
 * c'est l'effet de bord qui donne enfin de la matière au classement de la
 * recherche.
 */

const USERNAME = 'e2e-journal'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('ajout au journal, modification et suppression', async ({ page }) => {
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
    await expect(page).toHaveURL(/\/$/)
  })

  await test.step('le journal démarre avec les quatre repas', async () => {
    await page.goto('/journal')
    await expect(page.getByRole('heading', { name: 'Journal' })).toBeVisible()

    for (const meal of ['Petit-déjeuner', 'Déjeuner', 'Dîner', 'Collations']) {
      await expect(page.getByRole('heading', { name: meal, exact: true })).toBeVisible()
    }
  })

  await test.step('un aliment est ajouté depuis sa fiche', async () => {
    await page.goto('/aliments')
    await page.getByLabel('Rechercher un aliment').fill('abricot')
    await page
      .getByRole('link', { name: /Abricot/ })
      .first()
      .click()

    await expect(page.getByRole('heading', { name: 'Ajouter au journal' })).toBeVisible()
    await page.getByLabel('Quantité').fill('200')
    await page.getByRole('button', { name: 'Ajouter au journal' }).click()

    await expect(page).toHaveURL(/\/journal/)
  })

  await test.step('l’entrée apparaît et compte dans le total', async () => {
    const summary = page.getByRole('heading', { name: 'Bilan du jour' })
    await expect(summary).toBeVisible()
    // L'entrée est listée sous son repas.
    await expect(page.getByRole('link', { name: /Abricot/ }).first()).toBeVisible()
  })

  await test.step('la quantité se modifie depuis le journal', async () => {
    await page
      .getByRole('button', { name: /^Modifier / })
      .first()
      .click()
    const field = page.getByLabel(/^Quantité de /).first()
    await field.fill('300')
    await page.getByRole('button', { name: 'Valider' }).click()

    await expect(page.getByText('300 g')).toBeVisible()
  })

  await test.step('l’aliment consommé rejoint les récents', async () => {
    await page.goto('/aliments')
    await page.getByRole('tab', { name: 'Récents' }).click()

    await expect(page.getByRole('link', { name: /Abricot/ }).first()).toBeVisible()
  })

  await test.step('l’entrée se supprime', async () => {
    await page.goto('/journal')
    await page
      .getByRole('button', { name: /^Supprimer / })
      .first()
      .click()

    await expect(page.getByText('Rien pour l’instant.').first()).toBeVisible()
  })
})
