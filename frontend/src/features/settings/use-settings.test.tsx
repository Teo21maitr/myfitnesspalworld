import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { THEME_STORAGE_KEY } from '@/components/theme/theme-context'
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

const HEALTH = {
  status: 'ok',
  version: '0.1.0',
  time: '2026-08-24T10:00:00+02:00',
  checks: { database: 'ok', cache: 'ok' },
}

beforeEach(() => {
  seedCsrfCookie()
  window.localStorage.clear()
  document.documentElement.classList.remove('dark')
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
  window.localStorage.clear()
})

describe('Préférence de thème', () => {
  it('applique le thème enregistré sur le compte à la connexion', async () => {
    stubFetch([
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'dark', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/health/', respond: () => jsonResponse(HEALTH) },
    ])

    renderRoute('/')

    await waitFor(() => {
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })
  })

  it('enregistre le nouveau thème côté serveur', async () => {
    const user = userEvent.setup()
    let saved = 'system'

    const spy = stubFetch([
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: saved, date_format: 'DD/MM/YYYY' }),
      },
      { match: '/health/', respond: () => jsonResponse(HEALTH) },
    ])

    renderRoute('/')

    await user.click(await screen.findByRole('button', { name: 'Thème sombre' }))

    await waitFor(() => {
      const patch = spy.mock.calls.find(
        (call) =>
          String(call[0]).includes('/profile/settings/') &&
          (call[1] as RequestInit | undefined)?.method === 'PATCH',
      )
      expect(patch).toBeDefined()
      expect((patch?.[1] as RequestInit).body).toBe(JSON.stringify({ theme_mode: 'dark' }))
    })

    saved = 'dark'
    // La préférence reste également enregistrée localement pour éviter tout
    // clignotement au prochain chargement.
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })
})
