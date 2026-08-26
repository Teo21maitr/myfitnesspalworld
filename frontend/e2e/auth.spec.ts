import { expect, test } from '@playwright/test'

import { acceptRegistrationRequest, cleanupUser, resetThrottleCounters } from './helpers'

/**
 * Parcours complet du cycle de vie d'un compte (spec 08 §5) :
 *
 *   demande d'inscription → validation administrateur → connexion
 *   → onboarding → accès à une route privée → déconnexion
 */

const USERNAME = 'e2e-teo'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  // Le quota de connexion est volontairement serré (10/min). Chaque
  // parcours crée un compte et s'y connecte : à cinq parcours, le compteur
  // déborde. On le remet à zéro plutôt que d'affaiblir la protection.
  resetThrottleCounters()
  cleanupUser(USERNAME)
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('cycle de vie complet d’un compte', async ({ page }) => {
  await test.step('une route privée renvoie vers la connexion', async () => {
    await page.goto('/compte')
    await expect(page).toHaveURL(/\/connexion$/)
    await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible()
  })

  await test.step('dépôt de la demande d’inscription', async () => {
    await page.getByRole('link', { name: 'Demander un compte' }).click()
    await expect(page.getByRole('heading', { name: 'Demander un compte' })).toBeVisible()

    await page.getByLabel('Prénom').fill('Téo')
    await page.getByLabel('Nom', { exact: true }).fill('Maitrot')
    await page.getByLabel('Nom d’utilisateur').fill(USERNAME)
    await page.getByLabel('Mot de passe', { exact: true }).fill(PASSWORD)
    await page.getByLabel('Confirmation du mot de passe').fill(PASSWORD)
    await page.getByRole('button', { name: 'Envoyer ma demande' }).click()

    await expect(page.getByRole('heading', { name: 'Demande envoyée' })).toBeVisible()
  })

  await test.step('la demande en attente ne permet pas de se connecter', async () => {
    await page.goto('/connexion')
    await page.getByLabel('Nom d’utilisateur').fill(USERNAME)
    await page.getByLabel('Mot de passe').fill(PASSWORD)
    await page.getByRole('button', { name: 'Se connecter' }).click()

    // Tant que la demande n'est pas acceptée, aucun compte n'existe : le
    // message reste générique et ne révèle pas la demande en cours.
    await expect(page.getByRole('alert')).toHaveText('Nom d’utilisateur ou mot de passe incorrect.')
  })

  await test.step('validation par l’administrateur', () => {
    acceptRegistrationRequest(USERNAME)
  })

  await test.step('connexion', async () => {
    await page.goto('/connexion')
    await page.getByLabel('Nom d’utilisateur').fill(USERNAME)
    await page.getByLabel('Mot de passe').fill(PASSWORD)
    await page.getByRole('button', { name: 'Se connecter' }).click()

    // Le compte vient d'être créé : l'onboarding est obligatoire avant
    // d'atteindre l'application (spec 02 §1).
    await expect(page).toHaveURL(/\/onboarding$/)
    await expect(page.getByRole('heading', { name: 'Configurons vos objectifs' })).toBeVisible()
  })

  await test.step('onboarding — profil', async () => {
    await page.getByLabel('Date de naissance').fill('1996-01-01')
    await page.getByLabel('Sexe utilisé pour le calcul').selectOption('MALE')
    await page.getByLabel('Taille').fill('180')
    await page.getByLabel('Poids actuel').fill('80')
    await page.getByRole('button', { name: 'Continuer' }).click()
  })

  await test.step('onboarding — objectif, activité et rythme', async () => {
    await page.getByRole('radio', { name: /Perdre du poids/ }).check()
    await page.getByLabel('Poids cible (facultatif)').fill('75')
    await page.getByRole('button', { name: 'Continuer' }).click()

    await page.getByRole('radio', { name: /Modérément actif/ }).check()
    await page.getByRole('button', { name: 'Continuer' }).click()

    await page.getByRole('radio', { name: /0,5 kg par semaine/ }).check()
    await page.getByRole('button', { name: 'Continuer' }).click()
  })

  await test.step('onboarding — calories calculées par le serveur', async () => {
    // 10*80 + 6.25*180 - 5*30 + 5 = 1780 kcal de métabolisme de base,
    // 1780 * 1.55 = 2759 de dépense, moins 550 de déficit = 2209 kcal.
    await expect(page.getByText('2209 kcal')).toBeVisible()
    await expect(page.getByText(/estimation et non d’une recommandation médicale/)).toBeVisible()
    await page.getByRole('button', { name: 'Continuer' }).click()
  })

  await test.step('onboarding — macros et résumé', async () => {
    await expect(page.getByLabel('Protéines')).toHaveValue('166')
    await page.getByRole('button', { name: 'Continuer' }).click()

    await expect(page.getByText('Vos objectifs quotidiens')).toBeVisible()
    await page.getByRole('button', { name: 'Terminer' }).click()

    await expect(page).toHaveURL(/\/$/)
  })

  await test.step('les objectifs sont enregistrés', async () => {
    await page.goto('/objectifs')
    await expect(page.getByRole('heading', { name: 'Objectifs' })).toBeVisible()
    await expect(page.getByTestId('goal-summary')).toContainText('2209')
  })

  await test.step('accès à la zone privée', async () => {
    await page.goto('/compte')
    // `exact` évite la collision avec « Supprimer mon compte ».
    await expect(page.getByRole('heading', { name: 'Mon compte', exact: true })).toBeVisible()
    await expect(page.getByText(`Connecté en tant que ${USERNAME}`)).toBeVisible()
  })

  await test.step('déconnexion', async () => {
    await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click()
    await expect(page).toHaveURL(/\/connexion$/)
  })

  await test.step('la route privée est de nouveau refusée', async () => {
    await page.goto('/compte')
    await expect(page).toHaveURL(/\/connexion$/)
  })
})
