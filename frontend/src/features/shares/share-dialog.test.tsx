import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Friend } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { paginated } from '@/test/recipes'
import { renderWithProviders } from '@/test/render'

import { ShareDialog } from './share-dialog'

const BOB: Friend = {
  id: 2,
  username: 'bob',
  first_name: 'Bob',
  last_name: 'Martin',
  shares_diary: false,
  shares_progress: false,
}

function stub(friends: Friend[] = [BOB], create?: () => Response) {
  return stubFetch(
    [
      { match: '/auth/csrf/', respond: () => jsonResponse({ detail: 'ok' }) },
      { match: '/friends/', respond: () => jsonResponse(paginated(friends)) },
      {
        match: '/shares/',
        respond: create ?? (() => jsonResponse({ id: 9 }, 201)),
      },
    ],
    () => jsonResponse(paginated([])),
  )
}

function body(spy: ReturnType<typeof stubFetch>): unknown {
  const call = spy.mock.calls.find(
    ([url, init]) => String(url).includes('/shares/') && init?.method === 'POST',
  )
  return JSON.parse(String(call?.[1]?.body))
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('partage d’une ressource', () => {
  it('partage nommément à un ami choisi', async () => {
    const user = userEvent.setup()
    const spy = stub()
    renderWithProviders(<ShareDialog resourceType="recipe" resourceId={42} label="Blanquette" />)

    await user.click(screen.getByRole('button', { name: 'Partager Blanquette' }))
    await user.selectOptions(await screen.findByLabelText('Avec qui'), '2')
    await user.click(screen.getByRole('button', { name: 'Confirmer le partage' }))

    await waitFor(() =>
      expect(body(spy)).toEqual({
        resource_type: 'recipe',
        resource_id: 42,
        visibility: 'specific_user',
        target_user_id: 2,
      }),
    )
  })

  it('ouvre à tous les comptes actifs sans destinataire', async () => {
    const user = userEvent.setup()
    const spy = stub()
    renderWithProviders(<ShareDialog resourceType="recipe" resourceId={42} label="Blanquette" />)

    await user.click(screen.getByRole('button', { name: 'Partager Blanquette' }))
    await user.click(await screen.findByRole('button', { name: /Ouvrir à tous/ }))

    await waitFor(() =>
      expect(body(spy)).toMatchObject({ visibility: 'app_users', target_user_id: null }),
    )
  })

  it('envoie un identifiant nul pour le journal', async () => {
    // Le journal n'est pas une ligne : c'est l'ensemble des journées de son
    // propriétaire (spec 05 §8), et le backend refuse un identifiant.
    const user = userEvent.setup()
    const spy = stub()
    renderWithProviders(<ShareDialog resourceType="diary" label="mon journal" />)

    await user.click(screen.getByRole('button', { name: 'Partager mon journal' }))
    await user.click(await screen.findByRole('button', { name: /Ouvrir à tous/ }))

    await waitFor(() => expect(body(spy)).toMatchObject({ resource_id: null }))
  })

  it('envoie l’identifiant d’une liste de courses', async () => {
    // Le partage de liste était refusé en 400 : son type était rangé parmi
    // ceux qui n'ont pas d'identifiant.
    const user = userEvent.setup()
    const spy = stub()
    renderWithProviders(<ShareDialog resourceType="shopping_list" resourceId={7} label="Courses" />)

    await user.click(screen.getByRole('button', { name: 'Partager Courses' }))
    await user.click(await screen.findByRole('button', { name: /Ouvrir à tous/ }))

    await waitFor(() =>
      expect(body(spy)).toMatchObject({ resource_type: 'shopping_list', resource_id: 7 }),
    )
  })

  it('dit qu’un partage ciblé demande un ami', async () => {
    const user = userEvent.setup()
    stub([])
    renderWithProviders(<ShareDialog resourceType="recipe" resourceId={42} label="Blanquette" />)

    await user.click(screen.getByRole('button', { name: 'Partager Blanquette' }))

    expect(await screen.findByText(/pas encore d’amis/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirmer le partage' })).toBeNull()
  })

  it('n’envoie rien tant qu’aucun destinataire n’est choisi', async () => {
    const user = userEvent.setup()
    stub()
    renderWithProviders(<ShareDialog resourceType="recipe" resourceId={42} label="Blanquette" />)

    await user.click(screen.getByRole('button', { name: 'Partager Blanquette' }))

    expect(await screen.findByRole('button', { name: 'Confirmer le partage' })).toBeDisabled()
  })

  it('signale un refus du serveur', async () => {
    const user = userEvent.setup()
    stub([BOB], () =>
      jsonResponse({ code: 'validation_error', message: 'Partage refusé.', errors: {} }, 400),
    )
    renderWithProviders(<ShareDialog resourceType="recipe" resourceId={42} label="Blanquette" />)

    await user.click(screen.getByRole('button', { name: 'Partager Blanquette' }))
    await user.click(await screen.findByRole('button', { name: /Ouvrir à tous/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Partage refusé.')
  })
})
