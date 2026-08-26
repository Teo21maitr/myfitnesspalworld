import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

const MEAL = {
  id: 1,
  name: 'Petit-déjeuner',
  slug: 'petit-dejeuner',
  sort_order: 0,
  is_active: true,
  is_system: true,
  system_key: 'breakfast',
}

function stubQuickAdd() {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/meal-types/', respond: () => jsonResponse([MEAL]) },
      { match: '/diary/entries/', respond: () => jsonResponse({ id: 1 }, 201) },
      // L'ajout redirige vers le journal : la journée doit répondre.
      {
        match: '/diary/',
        respond: () =>
          jsonResponse({
            date: '2026-08-25',
            notes: '',
            goals: null,
            totals: { energy_kcal: null },
            incomplete_nutrients: [],
            remaining: null,
            meals: [],
          }),
      },
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

describe('Ajout rapide', () => {
  it('exige des calories avant d’autoriser l’envoi', async () => {
    stubQuickAdd()
    renderRoute('/ajout-rapide?date=2026-08-25')

    expect(await screen.findByRole('button', { name: 'Ajouter au journal' })).toBeDisabled()
  })

  it('accepte des calories seules', async () => {
    const user = userEvent.setup()
    const spy = stubQuickAdd()
    renderRoute('/ajout-rapide?date=2026-08-25')

    await user.type(await screen.findByLabelText('Calories'), '250')
    // Le bouton reste désactivé tant qu'aucun repas n'est chargé : cliquer
    // avant serait sans effet.
    await screen.findByRole('option', { name: 'Petit-déjeuner' })
    await user.click(screen.getByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => {
      // Filtrer aussi sur l'URL : le client peut poster un renouvellement
      // de session, qui est un POST sans corps.
      const post = spy.mock.calls.find(
        (call) =>
          (call[1] as RequestInit | undefined)?.method === 'POST' &&
          String(call[0]).includes('/diary/entries/'),
      )
      expect(post).toBeDefined()

      const body = JSON.parse(String((post?.[1] as RequestInit).body))
      expect(body.energy_kcal).toBe('250')
      expect(body.entry_type).toBe('quick_add')
      // Un macro laissé vide reste inconnu (spec 01 §8).
      expect(body.protein_g).toBeNull()
    })
  })

  it('transmet les macros saisies', async () => {
    const user = userEvent.setup()
    const spy = stubQuickAdd()
    renderRoute('/ajout-rapide?date=2026-08-25')

    await user.type(await screen.findByLabelText('Calories'), '250')
    await user.type(screen.getByLabelText('Protéines (g)'), '20')
    await screen.findByRole('option', { name: 'Petit-déjeuner' })
    await user.click(screen.getByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => {
      // Filtrer aussi sur l'URL : le client peut poster un renouvellement
      // de session, qui est un POST sans corps.
      const post = spy.mock.calls.find(
        (call) =>
          (call[1] as RequestInit | undefined)?.method === 'POST' &&
          String(call[0]).includes('/diary/entries/'),
      )
      const body = JSON.parse(String((post?.[1] as RequestInit).body))
      expect(body.protein_g).toBe('20')
    })
  })
})
