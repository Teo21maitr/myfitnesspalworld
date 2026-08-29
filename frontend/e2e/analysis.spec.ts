import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, resetThrottleCounters, signUp } from './helpers'

/**
 * Treizième parcours (spec 08 §5) : **la navigation au doigt**.
 *
 *   tiroir → planification → analyse → export
 *
 * Il existe pour une raison précise. La navigation vivait dans deux listes,
 * une par rendu, et chaque étape n'en remplissait qu'une : « Mes repas » avait
 * fini inatteignable sur mobile. Ce parcours traverse le tiroir plutôt que
 * `page.goto`, sur un écran de 375 px — la largeur d'un téléphone courant.
 * Aller directement à l'URL vérifierait que la page existe, pas qu'on peut
 * l'atteindre.
 */

const USERNAME = 'e2e-analyse'
const PASSWORD = 'un-mot-de-passe-e2e-1'

// Écran de téléphone : c'est le tiroir qui est rendu, pas la barre latérale.
test.use({ viewport: { width: 375, height: 812 } })

test.beforeAll(() => {
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('navigation mobile, analyse d’un nutriment et export', async ({ page }) => {
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

  await test.step('journaliser une entrée, pour avoir quelque chose à analyser', async () => {
    await page.goto('/ajout-rapide')
    await page.getByLabel('Intitulé (facultatif)').fill('Sandwich du midi')
    await page.getByLabel('Calories').fill('600')
    await page.getByRole('button', { name: 'Ajouter au journal' }).click()
    await expect(page).toHaveURL(/\/journal/)
  })

  const drawer = page.getByRole('navigation', { name: 'Menu de navigation' })

  await test.step('le tiroir mène à la planification', async () => {
    // La barre latérale n'existe pas à cette largeur : sans le tiroir, ces
    // destinations seraient hors d'atteinte.
    await expect(page.getByRole('navigation', { name: 'Navigation principale' })).toBeHidden()
    await expect(page.getByRole('navigation', { name: 'Raccourcis' })).toBeVisible()

    await page.getByRole('button', { name: 'Ouvrir la navigation' }).click()
    await drawer.getByRole('link', { name: 'Planification' }).click()

    await expect(page).toHaveURL(/\/planification$/)
    // Le tiroir se referme en changeant de page.
    await expect(drawer).toBeHidden()
  })

  await test.step('« Mes repas » est atteignable au doigt', async () => {
    // La destination qui était inatteignable avant cette étape.
    await page.getByRole('button', { name: 'Ouvrir la navigation' }).click()
    await drawer.getByRole('link', { name: 'Mes repas' }).click()

    await expect(page).toHaveURL(/\/mes-repas$/)
  })

  await test.step('l’analyse nomme la source du nutriment', async () => {
    await page.getByRole('button', { name: 'Ouvrir la navigation' }).click()
    await drawer.getByRole('link', { name: 'Analyse' }).click()

    await expect(page).toHaveURL(/\/analyse$/)
    const sources = page.getByRole('list', { name: 'Principales sources' })
    await expect(sources).toContainText('Sandwich du midi')
    await expect(sources).toContainText('100 %')
  })

  await test.step('les moyennes portent sur les journées tenues', async () => {
    await page.getByRole('button', { name: 'Ouvrir la navigation' }).click()
    await drawer.getByRole('link', { name: 'Rapports' }).click()

    await expect(page).toHaveURL(/\/rapports$/)
    // Une seule journée journalisée sur les trente de la période : la moyenne
    // vaut 600 kcal et non 600/30.
    await expect(page.getByText(/Moyennes calculées sur/)).toContainText(
      '1 journée journalisée, parmi les 30 jours',
    )
    await expect(page.getByText('Énergie').locator('..')).toContainText('600')
  })

  await test.step('chaque destination du tiroir s’ouvre au doigt', async () => {
    // La parité mobile/desktop est déjà garantie par un test unitaire qui
    // compare le routeur à la liste de navigation. Ici on vérifie l'autre
    // moitié : que chacune de ces destinations **s'affiche** sur un écran de
    // téléphone, sans se réduire à une page d'erreur.
    await page.getByRole('button', { name: 'Ouvrir la navigation' }).click()
    const labels = await drawer.getByRole('link').allInnerTexts()
    expect(labels.length).toBeGreaterThan(15)
    await drawer.getByRole('button', { name: 'Fermer la navigation' }).click()

    for (const label of labels) {
      await page.getByRole('button', { name: 'Ouvrir la navigation' }).click()
      await drawer.getByRole('link', { name: label, exact: true }).click()
      await expect(drawer).toBeHidden()
      await expect(page.getByRole('main').getByRole('heading').first()).toBeVisible()
      await expect(page.getByRole('main')).not.toContainText('Page introuvable')
    }
  })

  await test.step('exporter la période en CSV', async () => {
    await page.goto('/rapports')

    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'CSV' }).click()

    const file = await download
    expect(file.suggestedFilename()).toMatch(/^myfitnesspalworld-\d{8}-\d{8}\.csv$/)
  })
})
