import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FoodListItem } from '@/lib/api/types'
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

function food(overrides: Partial<FoodListItem> = {}): FoodListItem {
  return {
    id: 1,
    name: 'Poulet rôti',
    brand: '',
    source: 'ciqual',
    source_label: 'Ciqual',
    reference_amount: '100.00',
    reference_unit: 'g',
    energy_kcal: '192.000',
    is_favorite: false,
    is_own: false,
    is_verified: true,
    ...overrides,
  }
}

function page(results: FoodListItem[]) {
  return { count: results.length, next: null, previous: null, results }
}

interface StubOptions {
  searchResults?: FoodListItem[]
  favorites?: FoodListItem[]
  onSearch?: (url: string) => void
}

function stubFoods({ searchResults = [food()], favorites = [], onSearch }: StubOptions = {}) {
  return stubFetch([
    { match: '/auth/me/', respond: () => jsonResponse(USER) },
    {
      match: '/profile/settings/',
      respond: () =>
        jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
    },
    { match: '/foods/favorites/', respond: () => jsonResponse(page(favorites)) },
    { match: '/foods/recent/', respond: () => jsonResponse(page([])) },
    { match: '/foods/frequent/', respond: () => jsonResponse(page([])) },
    {
      match: '/foods/search/',
      respond: () => {
        onSearch?.('')
        return jsonResponse(page(searchResults))
      },
    },
  ])
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Recherche d’aliments', () => {
  it('affiche les favoris tant qu’aucune requête n’est saisie', async () => {
    stubFoods({ favorites: [food({ name: 'Yaourt nature' })] })
    renderRoute('/aliments')

    expect(await screen.findByRole('heading', { name: 'Aliments' })).toBeInTheDocument()
    expect(await screen.findByText('Yaourt nature')).toBeInTheDocument()
  })

  it('signale une liste de favoris vide', async () => {
    stubFoods()
    renderRoute('/aliments')

    expect(await screen.findByText(/Aucun favori pour le moment/)).toBeInTheDocument()
  })

  it('ne lance aucune recherche sous deux caractères', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    stubFoods({ onSearch })
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'p')

    expect(await screen.findByText(/au moins 2 caractères/)).toBeInTheDocument()
    expect(onSearch).not.toHaveBeenCalled()
  })

  it('affiche les résultats à partir de deux caractères', async () => {
    const user = userEvent.setup()
    stubFoods()
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'poulet')

    expect(await screen.findByText('Poulet rôti')).toBeInTheDocument()
    expect(screen.getByText('192')).toBeInTheDocument()
    // La source reste visible (spec 01 §8).
    expect(screen.getByText('Ciqual')).toBeInTheDocument()
  })

  it('signale une recherche sans résultat', async () => {
    const user = userEvent.setup()
    stubFoods({ searchResults: [] })
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'zzzz')

    expect(await screen.findByText(/Aucun aliment ne correspond/)).toBeInTheDocument()
  })

  it('bascule vers les récents', async () => {
    const user = userEvent.setup()
    stubFoods()
    renderRoute('/aliments')

    await user.click(await screen.findByRole('tab', { name: 'Récents' }))

    expect(await screen.findByText(/aliments que vous ajoutez à votre journal/)).toBeInTheDocument()
  })

  it('permet de mettre un résultat en favori', async () => {
    const user = userEvent.setup()
    const spy = stubFoods()
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'poulet')
    await user.click(await screen.findByRole('button', { name: /Ajouter Poulet rôti aux favoris/ }))

    await waitFor(() => {
      const calls = spy.mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/foods/1/favorite/'))).toBe(true)
    })
  })
})
