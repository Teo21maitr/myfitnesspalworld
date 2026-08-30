import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  makeReminderDue,
  resetThrottleCounters,
  runDueReminders,
  signUp,
} from './helpers'

/**
 * Quinzième parcours (spec 08 §5) : **les rappels et les notifications**.
 *
 *   régler un rappel → le rendre dû → balayer → le voir arriver
 *
 * Le balayage passe par le service réel, contrainte d'unicité comprise : c'est
 * le même chemin qu'en production. Il est lancé **deux fois**, parce que le
 * défaut que cette étape combat ne se voit qu'au second passage.
 */

const USERNAME = 'e2e-notifications'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('rappel réglé, déclenché et lu', async ({ page }) => {
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

  await test.step('la boîte est vide au départ', async () => {
    await page.goto('/notifications')
    await expect(page.getByText(/Rien pour l’instant/)).toBeVisible()
    await expect(page.getByLabel(/notification non lue/)).toHaveCount(0)
  })

  await test.step('régler un rappel de pesée', async () => {
    const row = page.getByRole('listitem', { name: 'Rappel Pesée' })
    await row.getByLabel('Heure').fill('08:00')
    await row.getByRole('button', { name: 'Activer le rappel Pesée' }).click()

    await expect(page.getByText('Rappel enregistré.')).toBeVisible()
  })

  await test.step('le balayage le déclenche, une seule fois', async () => {
    makeReminderDue(USERNAME)

    // Deux passages : c'est au second que le défaut se verrait.
    runDueReminders()
    runDueReminders()

    await page.reload()
    const list = page.getByRole('list', { name: 'Notifications' })
    await expect(list.getByText('Pesée du jour')).toHaveCount(1)
  })

  await test.step('la pastille compte les non-lues', async () => {
    await expect(page.getByLabel('1 notification non lue').first()).toBeVisible()
  })

  await test.step('la marquer lue éteint la pastille', async () => {
    await page.getByRole('button', { name: /Marquer .* comme lue/ }).click()

    await expect(page.getByLabel('1 notification non lue')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Tout marquer/ })).toHaveCount(0)
  })

  await test.step('le lien mène là où l’action se fait', async () => {
    await page
      .getByRole('list', { name: 'Notifications' })
      .getByRole('link', { name: 'Ouvrir' })
      .click()

    await expect(page).toHaveURL(/\/progression$/)
  })
})
