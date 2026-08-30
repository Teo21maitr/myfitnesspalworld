import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, resetThrottleCounters, signUp } from './helpers'

/**
 * Quatorzième parcours (spec 08 §5) : **les photos de progression**.
 *
 *   prendre → nommer l'angle → enregistrer → relire → supprimer
 *
 * Il tourne contre le **vrai** MinIO que `docker compose` fournit, et non
 * contre un stockage simulé : les tests unitaires vérifient que le code fait
 * ce qu'on a écrit, pas ce que le monde répond. C'est la leçon de l'étape 14.
 */

const USERNAME = 'e2e-photos'
const PASSWORD = 'un-mot-de-passe-e2e-1'

/** Les deux adresses du stockage, telles que `playwright.config.ts` les pose. */
const INTERNAL_ENDPOINT = process.env.E2E_S3_ENDPOINT_URL ?? 'http://127.0.0.1:9002'
const PUBLIC_ENDPOINT = process.env.E2E_S3_PUBLIC_ENDPOINT_URL ?? 'http://localhost:9002'

/** Un vrai JPEG minuscule : le serveur le rouvre pour le réencoder. */
const PHOTO = {
  name: 'progression.jpg',
  mimeType: 'image/jpeg',
  buffer: Buffer.from(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCABAADADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCeArJwAAAAAAAAAAAAAAAAAAAAAD//2Q==',
    'base64',
  ),
}

test.beforeAll(() => {
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('photos de progression : envoi, relecture et suppression', async ({ page }) => {
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

  await test.step('la progression mène aux photos', async () => {
    await page.goto('/progression')
    await page.getByRole('link', { name: 'Mes photos' }).click()

    await expect(page).toHaveURL(/\/photos$/)
    await expect(page.getByText(/jamais partageables/)).toBeVisible()
    await expect(page.getByText(/Aucune photo pour l’instant/)).toBeVisible()
  })

  await test.step('envoyer une photo et nommer son angle', async () => {
    await page.locator('input[type="file"]').setInputFiles(PHOTO)
    await page.getByRole('button', { name: 'Continuer' }).click()

    await page.getByLabel('Angle de la photo 1').selectOption('front')
    await page.getByLabel('Note (facultative)').fill('Point de départ')
    await page.getByRole('button', { name: 'Enregistrer' }).click()

    await expect(page.getByText('Photos enregistrées.')).toBeVisible()
  })

  await test.step('la photo se relit, servie par une URL signée', async () => {
    const gallery = page.getByRole('list', { name: 'Photos de progression' })
    const image = gallery.getByRole('img').first()

    await expect(image).toBeVisible()
    await expect(gallery).toContainText('Point de départ')

    // L'adresse pointe vers le seau, avec une signature — jamais vers l'API,
    // et jamais sans expiration (spec 05 §10).
    const source = await image.getAttribute('src')
    expect(source).toContain('X-Amz-Signature')
    expect(source).toContain('X-Amz-Expires')

    // Et elle porte l'adresse que **le navigateur** peut joindre, non celle du
    // réseau privé du backend : la configuration du parcours les distingue
    // exprès, parce que sous Docker elles diffèrent.
    //
    // L'attendu se lit dans la même variable que la configuration, jamais en
    // dur : un port codé ici passerait par coïncidence tant qu'il coïncide, et
    // mentirait le jour où il change.
    expect(source).toContain(new URL(PUBLIC_ENDPOINT).host)
    expect(source).not.toContain(new URL(INTERNAL_ENDPOINT).host)

    // Et elle affiche vraiment quelque chose : le seau a rendu les octets.
    await expect
      .poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth))
      .toBeGreaterThan(0)
  })

  await test.step('la suppression demande confirmation, puis efface', async () => {
    await page.getByRole('button', { name: /Supprimer les photos du/ }).click()
    await expect(page.getByText('Définitif ?')).toBeVisible()

    await page.getByRole('button', { name: 'Supprimer', exact: true }).click()

    await expect(page.getByText('Photos supprimées.')).toBeVisible()
    await expect(page.getByText(/Aucune photo pour l’instant/)).toBeVisible()
  })
})
