import { expect, test } from '@playwright/test'

import {
  acceptRegistrationRequest,
  cleanupUser,
  importCiqualSample,
  resetThrottleCounters,
  signUp,
} from './helpers'

/**
 * Parcours Meal Scan (spec 01, spec 07 §5, spec 08 §5) :
 *
 *   photographier un repas → suggestions → correction → journal
 *
 * Le fournisseur simulé renvoie volontairement une valeur nutritionnelle
 * fausse (`energy_kcal: 9999`). Ce parcours vérifie qu'elle n'apparaît nulle
 * part : ni dans les suggestions, ni dans le journal. C'est la règle la plus
 * fondamentale du projet — le modèle propose des mots, la base fournit les
 * calories (CLAUDE.md §2, spec 07 §1).
 */

// Caméra simulée par Chromium : le parcours ouvre un vrai flux, sans jamais
// allumer la caméra de la machine.
test.use({
  permissions: ['camera'],
  launchOptions: {
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  },
})

const USERNAME = 'e2e-meal-scan'
const PASSWORD = 'un-mot-de-passe-e2e-1'

/** Valeur inventée par le fournisseur simulé, qui ne doit jamais s'afficher. */
const INVENTED = '9999'

/** JPEG minimal : signature valide, contenu sans importance. */
const PHOTO = {
  name: 'repas.jpg',
  mimeType: 'image/jpeg',
  buffer: Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.alloc(64)]),
}

test.beforeAll(() => {
  // Dixième parcours : le quota de connexion de 10/min déborde sans remise à
  // zéro.
  resetThrottleCounters()
  cleanupUser(USERNAME)
  importCiqualSample()
})

test.afterAll(() => {
  cleanupUser(USERNAME)
})

test('analyse d’une photo, correction et journalisation', async ({ page }) => {
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

  await test.step('prendre la photo avec la caméra', async () => {
    // Chaque flux ouvert est retenu pour vérifier, plus bas, qu'il a bien été
    // relâché : une caméra ne s'éteint pas toute seule.
    await page.addInitScript(() => {
      const media = navigator.mediaDevices
      const original = media.getUserMedia.bind(media)
      const ouverts: MediaStream[] = []
      Object.assign(window, { __flux: ouverts })
      media.getUserMedia = async (contraintes?: MediaStreamConstraints) => {
        const flux = await original(contraintes)
        ouverts.push(flux)
        return flux
      }
    })

    await page.goto('/scanner-repas')
    await expect(page.getByRole('heading', { name: 'Scanner un repas' })).toBeVisible()

    await page.getByRole('button', { name: 'Ouvrir la caméra' }).click()
    await page.getByRole('button', { name: 'Prendre la photo' }).click()

    await expect(page.getByRole('button', { name: 'Retirer la photo 1' })).toBeVisible()
  })

  await test.step('l’import reste offert malgré la caméra', async () => {
    // Un geste ne doit jamais être l'unique moyen d'agir (spec 06 §6).
    await page.locator('input[type="file"]').setInputFiles(PHOTO)

    await expect(page.getByRole('button', { name: 'Retirer la photo 2' })).toBeVisible()
  })

  await test.step('lancer l’analyse', async () => {
    await page.getByRole('button', { name: 'Analyser' }).click()

    await expect(page.getByRole('heading', { name: 'Aliments détectés' })).toBeVisible()
  })

  await test.step('la caméra est éteinte pendant l’analyse', async () => {
    // Le piège de cette étape : un flux qui survit à l'écran qui l'a ouvert
    // laisse le voyant allumé sans qu'aucune erreur ne le signale.
    //
    // Cette vérification constate le résultat dans un vrai navigateur, mais ne
    // dit pas *lequel* des deux garde-fous a agi : la prise de vue est démontée
    // juste après, et son nettoyage suffirait. C'est le test unitaire de
    // `capture.tsx` qui distingue les deux.
    const etats = await page.evaluate(() =>
      ((window as unknown as { __flux: MediaStream[] }).__flux ?? [])
        .flatMap((flux) => flux.getTracks())
        .map((piste) => piste.readyState),
    )

    expect(etats.length).toBeGreaterThan(0)
    expect(etats.every((etat) => etat === 'ended')).toBe(true)
  })

  await test.step('les suggestions viennent de la base, pas de la photo', async () => {
    // Le cœur de l'étape.
    await expect(page.getByText('poulet', { exact: true })).toBeVisible()
    await expect(page.getByText('abricot', { exact: true })).toBeVisible()
    await expect(page.getByText('Confiance du modèle : 82 %')).toBeVisible()

    // La valeur inventée par le fournisseur n'a franchi aucune barrière.
    await expect(page.getByText(INVENTED)).toHaveCount(0)

    // Ce qui s'affiche vient de la fiche choisie.
    await expect(page.getByText(/d’après la fiche de l’aliment/).first()).toBeVisible()
  })

  await test.step('corriger une quantité puis confirmer', async () => {
    const quantity = page.getByLabel('Quantité').first()
    await quantity.fill('200')

    await page.getByRole('button', { name: 'Retirer abricot' }).click()
    await page.getByRole('button', { name: 'Ajouter au journal' }).click()

    await expect(page).toHaveURL(/\/journal$/)
  })

  await test.step('l’entrée est au journal, avec les valeurs de la base', async () => {
    await expect(page.getByRole('main')).toContainText(/Poulet/i)
    // Ni dans la ligne, ni dans les totaux de la journée.
    await expect(page.getByText(INVENTED)).toHaveCount(0)
  })
})
