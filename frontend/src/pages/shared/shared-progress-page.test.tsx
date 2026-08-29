import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ChartSeries, Friend } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const CAMILLE: Friend = {
  id: 2,
  username: 'camille',
  first_name: 'Camille',
  last_name: 'Rivet',
  shares_diary: true,
  shares_progress: true,
}

const SERIES: ChartSeries = {
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

function stubShared(chart: () => Response = () => jsonResponse(SERIES)) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/friends/', respond: () => jsonResponse(paginated([CAMILLE])) },
      { match: '/shared/progress/charts/', respond: chart },
    ],
    () => jsonResponse(paginated([])),
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('progression partagée', () => {
  it('affiche la courbe d’un ami', async () => {
    // Rien, nulle part, ne rendait cette page avec succès : le seul parcours
    // de bout en bout la visitait pour vérifier qu'elle échouait.
    stubShared()
    renderRoute('/amis/2/progression')

    expect(await screen.findByText('78 kg')).toBeInTheDocument()
  })

  it('dit de qui l’on regarde la progression', async () => {
    stubShared()
    renderRoute('/amis/2/progression')

    expect(
      await screen.findByRole('heading', { name: 'Progression de camille' }),
    ).toBeInTheDocument()
  })

  it('propose toutes les métriques, pas seulement le poids', async () => {
    const spy = stubShared()
    renderRoute('/amis/2/progression')
    await screen.findByText('78 kg')

    await userEvent.selectOptions(screen.getByLabelText('Mesure affichée'), 'waist')

    expect(spy.mock.calls.find(([url]) => String(url).includes('metric=waist'))).toBeDefined()
  })

  it('ne propose aucune action d’écriture', async () => {
    stubShared()
    renderRoute('/amis/2/progression')
    await screen.findByText('78 kg')

    // Portée à l'écran lui-même : la coquille de l'application porte son
    // propre bouton « + », qui ne touche pas aux données de l'ami.
    const page = within(screen.getByRole('main'))
    expect(page.queryByRole('button', { name: /Enregistrer|Supprimer|Ajouter/ })).toBeNull()
  })

  it('signale un partage absent plutôt qu’une page vide', async () => {
    stubShared(() =>
      jsonResponse({ code: 'not_found', message: 'Contenu introuvable.', errors: {} }, 404),
    )
    renderRoute('/amis/2/progression')

    expect(await screen.findByRole('alert')).toHaveTextContent('Contenu introuvable.')
  })

  it('refuse une adresse qui ne désigne aucun compte', async () => {
    // `Number('abc')` donne NaN : la requête restait désactivée et le
    // squelette tournait indéfiniment.
    stubShared()
    renderRoute('/amis/abc/progression')

    expect(await screen.findByRole('alert')).toHaveTextContent(/ne désigne aucun compte/)
    expect(screen.queryByText('Chargement de la courbe…')).toBeNull()
  })
})
