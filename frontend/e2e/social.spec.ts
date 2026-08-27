import { expect, test, type Page } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  importCiqualSample,
  signUp,
  resetThrottleCounters,
} from './helpers'

/**
 * Parcours social (spec 01 §17 et §18, spec 08 §5) :
 *
 *   s'inviter → accepter → partager une recette et son journal
 *   → consulter sans pouvoir modifier → retirer l'ami → tout perdre
 */

const ALICE = 'e2e-alice'
const BOB = 'e2e-bob'
const PASSWORD = 'un-mot-de-passe-e2e-1'

test.beforeAll(() => {
  // Huitième parcours, et deux comptes de plus : le quota de connexion de
  // 10/min déborde sans remise à zéro.
  resetThrottleCounters()
  cleanupUser(ALICE)
  cleanupUser(BOB)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(ALICE)
  cleanupUser(BOB)
})

/** Inscrit, valide et connecte un compte, onboarding compris. */
async function onboard(page: Page, username: string): Promise<void> {
  await signUp(page, username, PASSWORD)
  acceptRegistrationRequest(username)

  await page.goto('/connexion')
  await page.getByLabel('Nom d’utilisateur').fill(username)
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
}

/** Identifiant d'alice, lu depuis le lien que la page Partages propose. */
async function aliceId(page: Page): Promise<string> {
  await page.goto('/partages')
  const href = await page.getByRole('link', { name: 'Son journal' }).getAttribute('href')
  return href?.split('/')[2] ?? '0'
}

test('amitié, partage et révocation', async ({ browser }) => {
  // Deux contextes : deux sessions réellement distinctes, cookies compris.
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alice = await aliceContext.newPage()
  const bob = await bobContext.newPage()

  await test.step('deux comptes', async () => {
    await onboard(alice, ALICE)
    await onboard(bob, BOB)
  })

  await test.step('alice invite bob, bob accepte', async () => {
    await alice.goto('/amis')
    await alice.getByLabel('Chercher quelqu’un').fill(BOB)
    await alice.getByRole('button', { name: `Inviter ${BOB}` }).click()
    await expect(alice.getByText('Demande envoyée.')).toBeVisible()

    await bob.goto('/amis')
    await bob.getByRole('button', { name: `Accepter ${ALICE}` }).click()
    await expect(bob.getByText('Vous êtes amis.')).toBeVisible()
  })

  await test.step('alice compose une recette et la partage', async () => {
    await alice.goto('/recettes/nouvelle')
    await alice.getByLabel('Nom').fill('Compote d’alice')
    await alice.getByLabel('Portions').fill('2')
    await alice.getByLabel('Chercher un ingrédient').fill('abricot')
    await alice
      .getByRole('button', { name: /Abricot/ })
      .first()
      .click()
    await alice.getByRole('button', { name: /^Ajouter Abricot/ }).click()
    await alice.getByRole('button', { name: 'Créer la recette' }).click()
    await expect(alice).toHaveURL(/\/recettes\/\d+$/)

    await alice.getByRole('button', { name: /^Partager Compote/ }).click()
    await alice.getByLabel('Avec qui').selectOption({ label: BOB })
    await alice.getByRole('button', { name: 'Confirmer le partage' }).click()
    await expect(alice.getByText('Partagé.')).toBeVisible()
  })

  await test.step('bob voit la recette partagée', async () => {
    await bob.goto('/partages')
    await expect(bob.getByText('Compote d’alice')).toBeVisible()

    await bob.goto('/recettes')
    await expect(bob.getByRole('link', { name: /Compote d’alice/ })).toBeVisible()
  })

  await test.step('alice partage son journal', async () => {
    await alice.goto('/aliments')
    await alice.getByLabel('Rechercher un aliment').fill('abricot')
    await alice
      .getByRole('link', { name: /Abricot/ })
      .first()
      .click()
    await alice.getByLabel('Quantité').fill('200')
    await alice.getByRole('button', { name: 'Ajouter au journal' }).click()
    await expect(alice).toHaveURL(/\/journal/)

    await alice.goto('/partages')
    await alice.getByRole('button', { name: 'Partager mon journal' }).click()
    await alice.getByLabel('Avec qui').selectOption({ label: BOB })
    await alice.getByRole('button', { name: 'Confirmer le partage' }).click()
    await expect(alice.getByText('Partagé.')).toBeVisible()
  })

  await test.step('bob lit le journal partagé sans pouvoir le modifier', async () => {
    await bob.goto('/partages')
    await bob.getByRole('link', { name: 'Son journal' }).click()

    await expect(bob.getByRole('heading', { name: 'Journal partagé' })).toBeVisible()
    await expect(bob.getByText(/Abricot/).first()).toBeVisible()

    // Consultation seule : aucune action d'écriture n'est proposée.
    const page = bob.getByRole('main')
    await expect(page.getByRole('button', { name: /^Supprimer/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /^Modifier/ })).toHaveCount(0)
  })

  await test.step('la progression reste fermée', async () => {
    // Partager son journal ne partage pas sa progression (spec 01 §18).
    await bob.goto(`/amis/${await aliceId(bob)}/progression`)
    await expect(bob.getByRole('alert')).toBeVisible()
  })

  await test.step('alice retire bob et le partage disparaît', async () => {
    await alice.goto('/amis')
    await alice.getByRole('button', { name: `Retirer ${BOB}` }).click()
    await expect(alice.getByText(/partages qui le visaient sont révoqués/)).toBeVisible()

    await bob.goto('/partages')
    await expect(bob.getByText('Compote d’alice')).toHaveCount(0)

    await bob.goto('/recettes')
    await expect(bob.getByRole('link', { name: /Compote d’alice/ })).toHaveCount(0)
  })

  await aliceContext.close()
  await bobContext.close()
})
