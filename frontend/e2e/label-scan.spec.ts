import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, resetThrottleCounters, signUp } from './helpers'

/**
 * Parcours lecture d'étiquette (spec 01 §11, spec 07 §5) :
 *
 *   photographier une étiquette → brouillon → vérification → aliment créé
 *
 * Le fournisseur simulé laisse volontairement `fiber_g` nul. Ce parcours
 * vérifie que le champ reste vide et que l'écran le dit : un zéro affirmerait
 * que le produit ne contient pas de fibres, ce que la photo n'a pas montré
 * (spec 01 §8).
 */

test.use({
  permissions: ['camera'],
  launchOptions: {
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  },
})

const USERNAME = 'e2e-etiquette'
const PASSWORD = 'un-mot-de-passe-e2e-1'

const PHOTO = {
  name: 'etiquette.jpg',
  mimeType: 'image/jpeg',
  buffer: Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.alloc(64)]),
}

test.beforeAll(() => {
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('lecture d’une étiquette et création de l’aliment', async ({ page }) => {
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

  await test.step('photographier l’étiquette', async () => {
    await page.goto('/scanner-etiquette')
    await expect(page.getByRole('heading', { name: 'Créer depuis une étiquette' })).toBeVisible()

    // Les deux chemins, dans le même parcours : l'appareil photo et l'import.
    await page.getByRole('button', { name: 'Ouvrir la caméra' }).click()
    await page.getByRole('button', { name: 'Prendre la photo' }).click()
    await expect(page.getByRole('button', { name: 'Retirer la photo 1' })).toBeVisible()

    await page.locator('input[type="file"]').setInputFiles(PHOTO)
    await expect(page.getByRole('button', { name: 'Retirer la photo 2' })).toBeVisible()

    await page.getByRole('button', { name: 'Lire l’étiquette' }).click()
    await expect(page.getByRole('heading', { name: 'Ce que la photo a donné' })).toBeVisible()
  })

  await test.step('le formulaire est prérempli, et les manques sont nommés', async () => {
    await expect(page.getByLabel('Nom')).toHaveValue('Produit de démonstration')
    await expect(page.getByLabel('Marque (facultatif)')).toHaveValue('Marque simulée')
    await expect(page.getByLabel(/Énergie/)).toHaveValue('250')
    await expect(page.getByLabel(/dont sucres/)).toHaveValue('4.2')

    // Le cœur de l'étape : non lu n'est pas zéro.
    await expect(page.getByLabel(/Fibres/)).toHaveValue('')
    await expect(page.getByText(/La photo n’a pas donné/)).toContainText('fibres')
  })

  await test.step('l’aliment n’existe qu’après validation', async () => {
    await page.getByRole('button', { name: /Créer|Enregistrer/ }).click()

    await expect(page).toHaveURL(/\/aliments\/\d+$/)
    await expect(page.getByRole('heading', { name: 'Produit de démonstration' })).toBeVisible()
    // La valeur non lue reste inconnue sur la fiche, affichée « — ».
    await expect(page.getByText('Fibres').locator('..')).toContainText('—')
  })
})
