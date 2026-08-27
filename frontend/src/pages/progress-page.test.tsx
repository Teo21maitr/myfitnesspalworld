import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { today } from '@/features/diary/dates'
import type { BodyMeasurementEntry, ChartSeries, WeightEntry } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { renderRoute } from '@/test/render'

const USER = {
  id: 1,
  username: 'teo',
  first_name: 'Téo',
  last_name: 'Maitrot',
  email: null,
  status: 'ACTIVE',
  is_staff: false,
  onboarding_completed: true,
}

const CHART: ChartSeries = {
  metric: 'weight',
  unit: 'kg',
  from: '2026-05-29',
  to: '2026-08-26',
  points: [
    { date: '2026-08-20', value: '80.00', moving_average: '80.00' },
    { date: '2026-08-26', value: '78.00', moving_average: '79.00' },
  ],
  target: '70.00',
  trend_per_week: '-2.33',
}

function weight(date: string): WeightEntry {
  return {
    id: 1,
    date,
    weight_kg: '78.00',
    notes: null,
    created_at: '2026-08-26T08:00:00Z',
    updated_at: '2026-08-26T08:00:00Z',
  }
}

function measurement(date: string): BodyMeasurementEntry {
  return {
    id: 5,
    date,
    waist_cm: '85.0',
    hips_cm: null,
    chest_cm: null,
    arm_cm: null,
    thigh_cm: null,
    body_fat_percent: null,
    notes: null,
    created_at: '2026-08-26T08:00:00Z',
    updated_at: '2026-08-26T08:00:00Z',
  }
}

function page(list: unknown[]) {
  return { count: list.length, next: null, previous: null, results: list }
}

interface Stubs {
  chart?: () => Response
  weights?: () => Response
  measurements?: () => Response
}

function stubProgress({ chart, weights, measurements }: Stubs = {}) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/progress/charts/', respond: chart ?? (() => jsonResponse(CHART)) },
      { match: '/progress/weight/', respond: weights ?? (() => jsonResponse(page([]))) },
      {
        match: '/progress/measurements/',
        respond: measurements ?? (() => jsonResponse(page([]))),
      },
    ],
    () => jsonResponse(page([])),
  )
}

/** Requête envoyée vers cette route avec ce verbe.
 *
 * Le filtrage porte aussi sur l'URL : le client rafraîchit sa session par un
 * POST, qu'un filtre sur la seule méthode confondrait avec l'enregistrement.
 */
function requestTo(spy: ReturnType<typeof stubFetch>, path: string, method: string) {
  return spy.mock.calls.find(([url, init]) => String(url).includes(path) && init?.method === method)
}

/** Formulaire auquel appartient un champ.
 *
 * La page en porte deux, chacun avec son bouton « Enregistrer ».
 */
function formOf(field: HTMLElement): HTMLElement {
  return field.closest('form') as HTMLElement
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Progression', () => {
  it('affiche la courbe et sa tendance', async () => {
    stubProgress()
    renderRoute('/progression')

    expect(await screen.findByRole('heading', { name: 'Progression' })).toBeInTheDocument()
    expect(await screen.findByRole('img')).toHaveAccessibleName(/Poids du/)
    expect(screen.getByText(/Tendance −2,33 kg par semaine/)).toBeInTheDocument()
  })

  it('enregistre une pesée', async () => {
    const user = userEvent.setup()
    const spy = stubProgress()
    renderRoute('/progression')

    const field = await screen.findByLabelText('Poids (kg)')
    await user.type(field, '78,2')
    await user.click(within(formOf(field)).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(requestTo(spy, '/progress/weight/', 'POST')).toBeDefined())
    const body = JSON.parse(String(requestTo(spy, '/progress/weight/', 'POST')![1]?.body))
    expect(body).toMatchObject({ date: today(), weight_kg: '78.2' })
  })

  it('annonce le remplacement quand la date porte déjà une pesée', async () => {
    stubProgress({ weights: () => jsonResponse(page([weight(today())])) })
    renderRoute('/progression')

    expect(await screen.findByRole('button', { name: 'Mettre à jour' })).toBeInTheDocument()
    expect(screen.getByText(/Cette date porte déjà une pesée/)).toBeInTheDocument()
  })

  it('refuse d’enregistrer des mensurations vides', async () => {
    stubProgress()
    renderRoute('/progression')

    const form = formOf(await screen.findByLabelText('Tour de taille (cm)'))
    expect(within(form).getByRole('button', { name: 'Enregistrer' })).toBeDisabled()
  })

  it('enregistre une mensuration', async () => {
    const user = userEvent.setup()
    const spy = stubProgress()
    renderRoute('/progression')

    const field = await screen.findByLabelText('Tour de taille (cm)')
    await user.type(field, '85')
    await user.click(within(formOf(field)).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(requestTo(spy, '/progress/measurements/', 'POST')).toBeDefined())
    const body = JSON.parse(String(requestTo(spy, '/progress/measurements/', 'POST')![1]?.body))
    // Une mesure non saisie part `null`, jamais 0 (spec 01 §8).
    expect(body).toMatchObject({ waist_cm: '85', hips_cm: null })
  })

  it('reprend les mesures déjà relevées pour la date choisie', async () => {
    stubProgress({ measurements: () => jsonResponse(page([measurement(today())])) })
    renderRoute('/progression')

    const field = await screen.findByLabelText('Tour de taille (cm)')
    // Le champ existe avant que la requête ne réponde : c'est sa valeur qu'on attend.
    await waitFor(() => expect(field).toHaveValue('85'))
  })

  it('signale l’historique vide', async () => {
    stubProgress()
    renderRoute('/progression')

    expect(await screen.findByText(/Aucune pesée enregistrée/)).toBeInTheDocument()
    expect(screen.getByText(/Aucune mensuration enregistrée/)).toBeInTheDocument()
  })

  it('affiche un message lisible quand la courbe échoue', async () => {
    stubProgress({
      chart: () =>
        jsonResponse({ code: 'error', message: 'Service indisponible.', errors: {} }, 500),
    })
    renderRoute('/progression')

    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible.')
  })
})
