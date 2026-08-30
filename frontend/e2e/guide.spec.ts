import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, resetThrottleCounters, signUp } from './helpers'

/**
 * Guide d'utilisation et retour à l'accueil (spec 06 §4) :
 *
 *   arriver sur l'accueil → y trouver l'invitation → lire le guide
 *   → l'invitation disparaît → le logo ramène à l'accueil
 *
 * Les tests unitaires vérifient que la page décrit chaque écran. Ce qu'ils ne
 * peuvent pas voir : que l'invitation s'affiche à la première visite, qu'elle
 * s'efface ensuite, et que le logo est bien devenu un lien. Trois
 * comportements qui ne vivent que dans un vrai navigateur.
 */

const USERNAME = 'e2e-guide'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('guide d’utilisation et retour par le logo', async ({ page }) => {
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

  await test.step('l’accueil invite à lire le guide', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Première visite ?' })).toBeVisible()

    await page.getByRole('link', { name: 'Lire le guide' }).click()
    await expect(page).toHaveURL(/\/guide$/)
  })

  await test.step('le guide décrit les écrans et y mène', async () => {
    await expect(page.getByRole('heading', { name: 'Guide', level: 1 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Par où commencer' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Au quotidien' })).toBeVisible()

    // Restreint au contenu : la barre latérale porte les mêmes libellés.
    // Le guide sert aussi de sommaire — ses noms sont des liens.
    await page.getByRole('main').getByRole('link', { name: 'Journal', exact: true }).click()
    await expect(page).toHaveURL(/\/journal$/)
  })

  await test.step('l’invitation ne revient pas une fois le guide lu', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Aujourd’hui' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Première visite ?' })).toBeHidden()
  })

  await test.step('le logo ramène à l’accueil', async () => {
    await page.goto('/progression')
    await page.getByRole('link', { name: 'MyFitnessPalworld' }).click()

    await expect(page).toHaveURL((url) => url.pathname === '/')
    await expect(page.getByRole('heading', { name: 'Aujourd’hui' })).toBeVisible()
  })
})
