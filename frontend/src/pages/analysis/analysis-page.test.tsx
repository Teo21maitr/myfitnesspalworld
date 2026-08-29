import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { NutrientAnalysis } from '@/lib/api/types'
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

function analysis(overrides: Partial<NutrientAnalysis> = {}): NutrientAnalysis {
  return {
    nutrient: 'energy_kcal',
    label: 'Énergie (kcal)',
    from: '2026-08-01',
    to: '2026-08-30',
    total: '4200',
    sources: [
      { name: 'Poulet rôti', total: '3000', entries: 6, share: 71.4 },
      { name: 'Riz', total: '1200', entries: 3, share: 28.6 },
    ],
    unknown_entries: 0,
    logged_days: 5,
    is_partial: false,
    ...overrides,
  }
}

function stubAnalysis(respond: () => Response) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/analysis/food/', respond },
    ],
    () => jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('analyse', () => {
  it('classe les sources et affiche leur part', async () => {
    stubAnalysis(() => jsonResponse(analysis()))
    renderRoute('/analyse')

    await screen.findByText('Poulet rôti')

    // La liste est nommée : la navigation en rend d'autres dans le même arbre.
    const liste = screen.getByRole('list', { name: 'Principales sources' })
    const items = within(liste).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Poulet rôti')
    expect(items[0]).toHaveTextContent('71 %')
    expect(items[1]).toHaveTextContent('Riz')
  })

  it('dit sur combien de journées tenues porte la période', async () => {
    stubAnalysis(() => jsonResponse(analysis({ logged_days: 5 })))
    renderRoute('/analyse')

    expect(await screen.findByText(/5 journées journalisées/)).toBeInTheDocument()
  })

  it('annonce un total partiel plutôt que de laisser croire à cent pour cent', async () => {
    stubAnalysis(() =>
      jsonResponse(analysis({ is_partial: true, unknown_entries: 3, nutrient: 'fiber_g' })),
    )
    renderRoute('/analyse')

    const avertissement = await screen.findByText(/ne renseignent pas ce nutriment/)
    expect(avertissement).toHaveTextContent('3 entrées')
    expect(avertissement).toHaveTextContent(/minorants/)
  })

  it('affiche un tiret quand rien n’a été mesuré, jamais un zéro', async () => {
    stubAnalysis(() => jsonResponse(analysis({ total: null, sources: [], logged_days: 0 })))
    renderRoute('/analyse')

    expect(await screen.findByText('—')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('propose un état vide explicite', async () => {
    stubAnalysis(() => jsonResponse(analysis({ total: null, sources: [], logged_days: 0 })))
    renderRoute('/analyse')

    expect(await screen.findByText(/Aucun aliment n’a apporté ce nutriment/)).toBeInTheDocument()
  })

  it('signale une erreur sans casser l’écran', async () => {
    stubAnalysis(() =>
      jsonResponse({ code: 'server_error', message: 'Erreur serveur.', errors: {} }, 500),
    )
    renderRoute('/analyse')

    expect(await screen.findByRole('alert')).toHaveTextContent(/Erreur serveur/)
  })

  it('interroge le nutriment choisi', async () => {
    const spy = stubAnalysis(() => jsonResponse(analysis()))
    renderRoute('/analyse')
    await screen.findByText('Poulet rôti')

    await userEvent.selectOptions(screen.getByLabelText('Nutriment'), 'protein_g')

    await waitFor(() => {
      const appel = spy.mock.calls.find(([url]) => String(url).includes('nutrient=protein_g'))
      expect(appel).toBeDefined()
    })
  })

  it('n’offre pas les glucides nets, que le référentiel ne porte pas', async () => {
    stubAnalysis(() => jsonResponse(analysis()))
    renderRoute('/analyse')
    await screen.findByText('Poulet rôti')

    const options = within(screen.getByLabelText('Nutriment')).getAllByRole('option')
    expect(options.map((option) => option.getAttribute('value'))).not.toContain('net_carbs_g')
  })
})
