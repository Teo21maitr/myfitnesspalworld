import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FriendRequest, UserSummary } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const BOB: UserSummary = { id: 2, username: 'bob', first_name: 'Bob', last_name: 'Martin' }

function request(overrides: Partial<FriendRequest> = {}): FriendRequest {
  return {
    id: 5,
    from_user: BOB,
    to_user: { id: 1, username: 'teo', first_name: 'Téo', last_name: 'Maitrot' },
    status: 'pending',
    direction: 'received',
    created_at: '2026-08-26T08:00:00Z',
    ...overrides,
  }
}

interface Stubs {
  friends?: UserSummary[]
  requests?: FriendRequest[]
  search?: UserSummary[]
}

function stubSocial({ friends = [], requests = [], search = [BOB] }: Stubs = {}) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/users/search/', respond: () => jsonResponse(paginated(search)) },
      { match: '/friend-requests/', respond: () => jsonResponse(paginated(requests)) },
      { match: '/friends/', respond: () => jsonResponse(paginated(friends)) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function sent(spy: ReturnType<typeof stubFetch>, path: string, method: string) {
  return spy.mock.calls.find(([url, init]) => String(url).includes(path) && init?.method === method)
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Amis', () => {
  it('annonce que le partage suppose une amitié', async () => {
    stubSocial()
    renderRoute('/amis')

    expect(await screen.findByRole('heading', { name: 'Amis' })).toBeInTheDocument()
    expect(screen.getByText(/retirer quelqu’un révoque/i)).toBeInTheDocument()
  })

  it('précise que la recherche ne porte pas sur l’email', async () => {
    // La spec 01 §1 l'exclut : le dire évite qu'on la cherche.
    stubSocial()
    renderRoute('/amis')

    expect(await screen.findByText(/jamais sur l’adresse email/)).toBeInTheDocument()
  })

  it('n’interroge pas le serveur sous deux caractères', async () => {
    const user = userEvent.setup()
    const spy = stubSocial()
    renderRoute('/amis')

    await user.type(await screen.findByLabelText('Chercher quelqu’un'), 'b')

    expect(sent(spy, '/users/search/', 'GET')).toBeUndefined()
  })

  it('invite un compte trouvé', async () => {
    const user = userEvent.setup()
    const spy = stubSocial()
    renderRoute('/amis')

    await user.type(await screen.findByLabelText('Chercher quelqu’un'), 'bob')
    await user.click(await screen.findByRole('button', { name: 'Inviter bob' }))

    await waitFor(() => expect(sent(spy, '/friend-requests/', 'POST')).toBeDefined())
    const body = JSON.parse(String(sent(spy, '/friend-requests/', 'POST')![1]?.body))
    expect(body).toEqual({ to_user_id: 2 })
  })

  it('accepte une demande reçue', async () => {
    const user = userEvent.setup()
    const spy = stubSocial({ requests: [request()] })
    renderRoute('/amis')

    await user.click(await screen.findByRole('button', { name: 'Accepter bob' }))

    await waitFor(() => expect(sent(spy, '/accept/', 'POST')).toBeDefined())
  })

  it('n’offre pas de répondre à une demande qu’on a envoyée', async () => {
    stubSocial({ requests: [request({ direction: 'sent' })] })
    renderRoute('/amis')

    expect(await screen.findByText('invitation envoyée')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Accepter/ })).not.toBeInTheDocument()
  })

  it('retire un ami', async () => {
    // Le message annonçant la révocation passe par un toast, vérifié par le
    // parcours de bout en bout.
    const user = userEvent.setup()
    const spy = stubSocial({ friends: [BOB] })
    renderRoute('/amis')

    await user.click(await screen.findByRole('button', { name: 'Retirer bob' }))

    await waitFor(() => expect(sent(spy, '/friends/2/', 'DELETE')).toBeDefined())
  })

  it('mène au journal et à la progression d’un ami', async () => {
    stubSocial({ friends: [BOB] })
    renderRoute('/amis')

    const row = (await screen.findByText('bob')).closest('li') as HTMLElement
    expect(within(row).getByRole('link', { name: 'Son journal' })).toHaveAttribute(
      'href',
      '/amis/2/journal',
    )
    expect(within(row).getByRole('link', { name: 'Sa progression' })).toHaveAttribute(
      'href',
      '/amis/2/progression',
    )
  })

  it('invite à chercher quand on n’a pas encore d’amis', async () => {
    stubSocial()
    renderRoute('/amis')

    expect(await screen.findByText(/Personne pour l’instant/)).toBeInTheDocument()
  })
})
