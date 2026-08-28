import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function stubAccount() {
  return stubFetch(
    [
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({
            language: 'fr',
            theme_mode: 'system',
            date_format: 'DD/MM/YYYY',
            food_search_languages: ['fr', 'en'],
            available_food_search_languages: [
              { code: 'en', label: 'Anglais' },
              { code: 'fr', label: 'Français' },
              { code: 'sv', label: 'Suédois' },
            ],
          }),
      },
      ...BASE_ROUTES,
      {
        match: '/health/',
        respond: () =>
          jsonResponse({
            status: 'ok',
            version: '0.1.0',
            time: '2026-08-28T12:00:00Z',
            checks: { database: 'ok', cache: 'ok' },
          }),
      },
    ],
    () => jsonResponse(paginated([])),
  )
}

/** Corps du dernier PATCH envoyé aux réglages. */
function patchedLanguages(spy: ReturnType<typeof stubFetch>): unknown {
  const call = spy.mock.calls
    .filter(([url, init]) => String(url).includes('/profile/settings/') && init?.method === 'PATCH')
    .at(-1)
  return call ? JSON.parse(String(call[1]?.body)) : undefined
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('langues de recherche', () => {
  it('affiche le catalogue servi par le serveur', async () => {
    stubAccount()
    renderRoute('/compte')

    expect(await screen.findByLabelText('Suédois')).toBeInTheDocument()
    expect(screen.getByLabelText('Français')).toBeChecked()
    expect(screen.getByLabelText('Suédois')).not.toBeChecked()
  })

  it('ajoute une langue', async () => {
    const user = userEvent.setup()
    const spy = stubAccount()
    renderRoute('/compte')

    await user.click(await screen.findByLabelText('Suédois'))

    await waitFor(() =>
      expect(patchedLanguages(spy)).toEqual({ food_search_languages: ['fr', 'en', 'sv'] }),
    )
  })

  it('retire une langue', async () => {
    const user = userEvent.setup()
    const spy = stubAccount()
    renderRoute('/compte')

    await user.click(await screen.findByLabelText('Anglais'))

    await waitFor(() => expect(patchedLanguages(spy)).toEqual({ food_search_languages: ['fr'] }))
  })

  it('n’offre pas de retirer la dernière langue', async () => {
    // Chercher dans aucune langue ne renverrait rien : le geste est empêché
    // plutôt que refusé par le serveur.
    stubFetch(
      [
        {
          match: '/profile/settings/',
          respond: () =>
            jsonResponse({
              language: 'fr',
              theme_mode: 'system',
              date_format: 'DD/MM/YYYY',
              food_search_languages: ['fr'],
              available_food_search_languages: [
                { code: 'fr', label: 'Français' },
                { code: 'sv', label: 'Suédois' },
              ],
            }),
        },
        ...BASE_ROUTES,
        {
          match: '/health/',
          respond: () =>
            jsonResponse({
              status: 'ok',
              version: '0.1.0',
              time: '2026-08-28T12:00:00Z',
              checks: { database: 'ok', cache: 'ok' },
            }),
        },
      ],
      () => jsonResponse(paginated([])),
    )
    renderRoute('/compte')

    expect(await screen.findByLabelText('Français')).toBeDisabled()
    expect(screen.getByLabelText('Suédois')).toBeEnabled()
  })
})
