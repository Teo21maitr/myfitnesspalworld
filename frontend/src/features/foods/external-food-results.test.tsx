import { screen } from '@testing-library/react'
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
    name: 'Pâte à tartiner',
    brand: '',
    source: 'ciqual',
    source_label: 'Ciqual',
    reference_amount: '100.00',
    reference_unit: 'g',
    energy_kcal: '539.000',
    is_favorite: false,
    is_own: false,
    is_verified: true,
    ...overrides,
  }
}

interface StubOptions {
  external?: () => Response
  onExternal?: () => void
}

function stubSearch({ external, onExternal }: StubOptions = {}) {
  return stubFetch([
    { match: '/auth/me/', respond: () => jsonResponse(USER) },
    {
      match: '/profile/settings/',
      respond: () =>
        jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
    },
    {
      match: '/foods/external-search/',
      respond: () => {
        onExternal?.()
        return external
          ? external()
          : jsonResponse({
              results: [
                { code: '3017620422003', name: 'Nutella', brand: 'Ferrero', food_id: null },
              ],
            })
      },
    },
    { match: '/foods/favorites/', respond: () => jsonResponse({ count: 0, results: [] }) },
    { match: '/foods/recent/', respond: () => jsonResponse({ count: 0, results: [] }) },
    { match: '/foods/frequent/', respond: () => jsonResponse({ count: 0, results: [] }) },
    {
      match: '/foods/search/',
      respond: () => jsonResponse({ count: 1, results: [food()] }),
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

describe('Recherche élargie à Open Food Facts', () => {
  it('n’interroge pas la source tant que l’utilisateur ne le demande pas', async () => {
    const user = userEvent.setup()
    const onExternal = vi.fn()
    stubSearch({ onExternal })
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'nutella')
    await screen.findByText('Pâte à tartiner')

    // Le quota est partagé par tous les comptes : jamais d'appel à la frappe
    // (spec 11 §5).
    expect(onExternal).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Chercher sur Open Food Facts/ })).toBeInTheDocument()
  })

  it('affiche les produits de marque après demande explicite', async () => {
    const user = userEvent.setup()
    stubSearch()
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'nutella')
    await user.click(await screen.findByRole('button', { name: /Chercher sur Open Food Facts/ }))

    expect(await screen.findByText('Nutella')).toBeInTheDocument()
    expect(screen.getByText('Ferrero')).toBeInTheDocument()
  })

  it('signale l’indisponibilité sans masquer les résultats locaux', async () => {
    const user = userEvent.setup()
    stubSearch({
      external: () =>
        jsonResponse(
          {
            code: 'external_source_unavailable',
            message: 'Open Food Facts est momentanément indisponible.',
            errors: {},
          },
          503,
        ),
    })
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'nutella')
    await user.click(await screen.findByRole('button', { name: /Chercher sur Open Food Facts/ }))

    expect(await screen.findByText(/momentanément indisponible/)).toBeInTheDocument()
    // La recherche locale continue de fonctionner (spec 11 §3).
    expect(screen.getByText('Pâte à tartiner')).toBeInTheDocument()
  })

  it('signale une recherche sans résultat', async () => {
    const user = userEvent.setup()
    stubSearch({ external: () => jsonResponse({ results: [] }) })
    renderRoute('/aliments')

    await user.type(await screen.findByLabelText('Rechercher un aliment'), 'nutella')
    await user.click(await screen.findByRole('button', { name: /Chercher sur Open Food Facts/ }))

    expect(await screen.findByText(/Aucun produit trouvé/)).toBeInTheDocument()
  })
})
