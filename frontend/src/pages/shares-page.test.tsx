import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SharePermission, UserSummary } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const ME: UserSummary = { id: 1, username: 'teo', first_name: 'Téo', last_name: 'Maitrot' }
const BOB: UserSummary = { id: 2, username: 'bob', first_name: 'Bob', last_name: 'Martin' }

function share(overrides: Partial<SharePermission> = {}): SharePermission {
  return {
    id: 7,
    owner: ME,
    target_user: BOB,
    resource_type: 'recipe',
    resource_id: 3,
    resource_name: 'Blanquette',
    visibility: 'specific_user',
    created_at: '2026-08-26T08:00:00Z',
    ...overrides,
  }
}

function stubShares(granted: SharePermission[] = [], received: SharePermission[] = []) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/shares/received/', respond: () => jsonResponse(paginated(received)) },
      { match: '/shares/', respond: () => jsonResponse(paginated(granted)) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function card(title: string): HTMLElement {
  return screen.getByRole('heading', { name: title }).closest('[data-slot="card"]') as HTMLElement
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Partages', () => {
  it('rappelle que tout est privé par défaut', async () => {
    stubShares()
    renderRoute('/partages')

    expect(await screen.findByRole('heading', { name: 'Partages' })).toBeInTheDocument()
    expect(screen.getByText(/privé par défaut/)).toBeInTheDocument()
  })

  it('liste ce que je partage et avec qui', async () => {
    stubShares([share()])
    renderRoute('/partages')

    await screen.findByText('Blanquette')
    const granted = within(card('Ce que je partage'))
    expect(granted.getByText(/Recette · bob/)).toBeInTheDocument()
  })

  it('nomme un partage ouvert à tous', async () => {
    stubShares([share({ target_user: null, visibility: 'app_users' })])
    renderRoute('/partages')

    expect(await screen.findByText(/tous les comptes actifs/)).toBeInTheDocument()
  })

  it('révoque un partage', async () => {
    const user = userEvent.setup()
    const spy = stubShares([share()])
    renderRoute('/partages')

    await user.click(
      await screen.findByRole('button', { name: 'Révoquer le partage de Blanquette' }),
    )

    await waitFor(() =>
      expect(
        spy.mock.calls.find(
          ([url, init]) => String(url).includes('/shares/7/') && init?.method === 'DELETE',
        ),
      ).toBeDefined(),
    )
  })

  it('mène au journal partagé qu’on a reçu', async () => {
    stubShares(
      [],
      [share({ owner: BOB, target_user: ME, resource_type: 'diary', resource_id: null })],
    )
    renderRoute('/partages')

    const link = await screen.findByRole('link', { name: 'Son journal' })
    expect(link).toHaveAttribute('href', '/amis/2/journal')
  })

  it('signale les deux listes vides', async () => {
    stubShares()
    renderRoute('/partages')

    expect(await screen.findByText(/Le bouton « Partager »/)).toBeInTheDocument()
    expect(screen.getByText('Rien pour l’instant.')).toBeInTheDocument()
  })
})
