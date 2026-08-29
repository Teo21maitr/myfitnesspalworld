import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { PeriodReport } from '@/lib/api/types'
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

function report(overrides: Partial<PeriodReport> = {}): PeriodReport {
  return {
    from: '2026-08-24',
    to: '2026-08-30',
    days: [],
    averages: {
      energy_kcal: '2000.00',
      protein_g: '120.00',
      carbohydrates_g: '200.00',
      fat_g: '70.00',
      fiber_g: null,
    },
    adherence: { days_measured: 5, days_within_goal: 3 },
    top_foods: [],
    logged_days: 5,
    calendar_days: 7,
    weight_change: '-1.50',
    weight: {
      points: [
        { date: '2026-08-24', value: '80.00', moving_average: '80.00' },
        { date: '2026-08-30', value: '78.50', moving_average: '79.25' },
      ],
      target: '70.00',
      trend_per_week: '-1.50',
    },
    ...overrides,
  }
}

function pdfResponse(): Response {
  return new Response(new Blob([new Uint8Array([37, 80, 68, 70])]), {
    status: 200,
    headers: { 'Content-Type': 'application/pdf' },
  })
}

function stubReports(respond?: () => Response, exportResponse?: () => Response) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/reports/summary/', respond: respond ?? (() => jsonResponse(report())) },
      { match: '/reports/csv/', respond: exportResponse ?? pdfResponse },
      { match: '/reports/pdf/', respond: exportResponse ?? pdfResponse },
    ],
    () => jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
}

beforeEach(() => {
  seedCsrfCookie()
  // jsdom n'implémente ni la création d'URL d'objet ni le téléchargement.
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x') }))
  URL.revokeObjectURL = vi.fn()
  HTMLAnchorElement.prototype.click = vi.fn()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  clearCsrfCookie()
})

describe('rapports', () => {
  it('dit sur combien de journées tenues portent les moyennes', async () => {
    stubReports()
    renderRoute('/rapports')

    const phrase = await screen.findByText(/Moyennes calculées sur/)
    expect(phrase).toHaveTextContent('5 journées journalisées, parmi les 7 jours')
  })

  it('affiche un tiret pour une moyenne jamais mesurée', async () => {
    stubReports()
    renderRoute('/rapports')

    await screen.findByText('Énergie')

    const fibres = screen.getByText('Fibres').closest('div') as HTMLElement
    expect(fibres).toHaveTextContent('—')
  })

  it('annonce le respect de l’objectif', async () => {
    stubReports()
    renderRoute('/rapports')

    expect(await screen.findByText(/3 journées sur 5/)).toBeInTheDocument()
  })

  it('distingue une période vide d’une période à zéro', async () => {
    stubReports(() =>
      jsonResponse(
        report({
          logged_days: 0,
          days: [],
          averages: { energy_kcal: null },
          adherence: { days_measured: 0, days_within_goal: 0 },
          weight_change: null,
          weight: { points: [], target: null, trend_per_week: null },
        }),
      ),
    )
    renderRoute('/rapports')

    expect(await screen.findByText(/ce n’est pas la même chose que zéro/)).toBeInTheDocument()
  })

  it('dit qu’aucun objectif n’était applicable plutôt que d’afficher zéro sur zéro', async () => {
    stubReports(() =>
      jsonResponse(report({ adherence: { days_measured: 0, days_within_goal: 0 } })),
    )
    renderRoute('/rapports')

    expect(await screen.findByText(/Aucun objectif applicable/)).toBeInTheDocument()
  })

  it('exporte la période affichée en CSV', async () => {
    const spy = stubReports()
    renderRoute('/rapports')
    await screen.findByText('Énergie')

    await userEvent.click(screen.getByRole('button', { name: 'CSV' }))

    await waitFor(() => {
      const appel = spy.mock.calls.find(([url]) => String(url).includes('/reports/csv/'))
      expect(appel).toBeDefined()
      expect(JSON.parse(String(appel?.[1]?.body))).toEqual({
        from: expect.any(String),
        to: expect.any(String),
      })
    })
  })

  it('signale un export en échec', async () => {
    stubReports(undefined, () =>
      jsonResponse({ code: 'server_error', message: 'Erreur serveur.', errors: {} }, 500),
    )
    renderRoute('/rapports')
    await screen.findByText('Énergie')

    await userEvent.click(screen.getByRole('button', { name: 'PDF' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Erreur serveur/)
  })
})
