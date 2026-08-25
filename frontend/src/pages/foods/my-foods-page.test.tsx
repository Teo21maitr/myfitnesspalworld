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

const MINE: FoodListItem = {
  id: 12,
  name: 'Granola maison',
  brand: '',
  source: 'user',
  source_label: 'Utilisateur',
  reference_amount: '100.00',
  reference_unit: 'g',
  energy_kcal: '450.000',
  is_favorite: false,
  is_own: true,
  is_verified: false,
}

interface StubOptions {
  mine?: FoodListItem[]
}

function stubMyFoods({ mine = [] }: StubOptions = {}) {
  return stubFetch([
    { match: '/auth/me/', respond: () => jsonResponse(USER) },
    {
      match: '/profile/settings/',
      respond: () =>
        jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
    },
    {
      match: '/foods/',
      respond: () =>
        jsonResponse({ count: mine.length, next: null, previous: null, results: mine }),
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

describe('Mes aliments', () => {
  it('signale une liste vide', async () => {
    stubMyFoods()
    renderRoute('/mes-aliments')

    expect(await screen.findByRole('heading', { name: 'Mes aliments' })).toBeInTheDocument()
    expect(await screen.findByText(/pas encore créé d’aliment/)).toBeInTheDocument()
  })

  it('liste les aliments personnels', async () => {
    stubMyFoods({ mine: [MINE] })
    renderRoute('/mes-aliments')

    expect(await screen.findByText('Granola maison')).toBeInTheDocument()
    expect(screen.getByText('450')).toBeInTheDocument()
  })

  it('ouvre le formulaire de création', async () => {
    const user = userEvent.setup()
    stubMyFoods()
    renderRoute('/mes-aliments')

    await user.click(await screen.findByRole('button', { name: /Créer/ }))

    expect(await screen.findByRole('heading', { name: 'Nouvel aliment' })).toBeInTheDocument()
    expect(screen.getByLabelText('Nom')).toBeInTheDocument()
    expect(screen.getByLabelText('Énergie')).toBeInTheDocument()
  })

  it('valide les champs obligatoires du formulaire', async () => {
    const user = userEvent.setup()
    stubMyFoods()
    renderRoute('/mes-aliments')

    await user.click(await screen.findByRole('button', { name: /Créer/ }))
    await user.click(screen.getByRole('button', { name: 'Créer l’aliment' }))

    expect(await screen.findByText(/au moins 2 caractères/)).toBeInTheDocument()
    expect(screen.getByText('L’énergie est obligatoire.')).toBeInTheDocument()
  })

  it('envoie les champs vides en null plutôt qu’en zéro', async () => {
    const user = userEvent.setup()
    const spy = stubFetch([
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/auth/csrf/', respond: () => jsonResponse({ detail: 'ok' }) },
      {
        match: '/foods/',
        respond: () => jsonResponse({ count: 0, next: null, previous: null, results: [] }),
      },
    ])
    renderRoute('/mes-aliments')

    await user.click(await screen.findByRole('button', { name: /Créer/ }))
    await user.type(screen.getByLabelText('Nom'), 'Granola maison')
    await user.type(screen.getByLabelText('Énergie'), '450')
    await user.click(screen.getByRole('button', { name: 'Créer l’aliment' }))

    await waitFor(() => {
      const post = spy.mock.calls.find(
        (call) => (call[1] as RequestInit | undefined)?.method === 'POST',
      )
      expect(post).toBeDefined()

      const body = JSON.parse(String((post?.[1] as RequestInit).body))
      expect(body.nutrition.energy_kcal).toBe('450')
      // Un champ laissé vide reste inconnu (spec 01 §8).
      expect(body.nutrition.protein_g).toBeNull()
    })
  })
})
