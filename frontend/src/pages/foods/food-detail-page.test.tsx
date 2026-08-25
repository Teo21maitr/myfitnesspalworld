import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FoodDetail } from '@/lib/api/types'
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

const NUTRITION = {
  energy_kcal: '45.900',
  protein_g: '0.810',
  carbohydrates_g: '9.010',
  fat_g: '0.000',
  fiber_g: '1.700',
  sugars_g: null,
  sodium_mg: null,
  salt_g: '0.000',
  cholesterol_mg: null,
  potassium_mg: null,
  calcium_mg: null,
  iron_mg: null,
  magnesium_mg: null,
  vitamin_a_ug: '391.667',
  vitamin_b6_mg: null,
  vitamin_b12_ug: null,
  vitamin_c_mg: '2.550',
  vitamin_d_ug: null,
  vitamin_e_mg: null,
  vitamin_k_ug: null,
  net_carbs_g: '7.310',
}

function detail(overrides: Partial<FoodDetail> = {}): FoodDetail {
  return {
    id: 7,
    name: 'Abricot, dénoyauté, cru',
    brand: '',
    source: 'ciqual',
    source_label: 'Ciqual',
    reference_amount: '100.00',
    reference_unit: 'g',
    energy_kcal: '45.900',
    is_favorite: false,
    is_own: false,
    is_verified: true,
    barcode: null,
    visibility: 'private',
    default_unit_type: 'g',
    nutrition: NUTRITION,
    portions: [],
    is_editable: false,
    created_at: '2026-08-01T10:00:00+02:00',
    updated_at: '2026-08-01T10:00:00+02:00',
    ...overrides,
  }
}

function stubDetail(food: FoodDetail = detail(), onWrite?: (url: string) => void) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/foods/7/portions/', respond: () => jsonResponse({ id: 1 }, 201) },
      { match: '/foods/7/favorite/', respond: () => new Response(null, { status: 204 }) },
      { match: '/foods/7/', respond: () => jsonResponse(food) },
    ],
    () => {
      onWrite?.('')
      return jsonResponse({ count: 0, next: null, previous: null, results: [] })
    },
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Fiche aliment', () => {
  it('affiche le nom, la source et les valeurs connues', async () => {
    stubDetail()
    renderRoute('/aliments/7')

    expect(
      await screen.findByRole('heading', { name: 'Abricot, dénoyauté, cru' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Source : Ciqual/)).toBeInTheDocument()
    expect(screen.getByText('45,9')).toBeInTheDocument()
  })

  it('affiche « — » pour les valeurs inconnues et jamais 0', async () => {
    stubDetail()
    renderRoute('/aliments/7')

    await screen.findByRole('heading', { name: 'Abricot, dénoyauté, cru' })

    // 9 nutriments valent null dans cette fiche.
    expect(screen.getAllByText('—').length).toBeGreaterThan(5)
    // Le sel vaut zéro : c'est une mesure, pas une absence.
    expect(screen.getByText('Sel').closest('div')).toHaveTextContent('0')
  })

  it('affiche les glucides nets', async () => {
    stubDetail()
    renderRoute('/aliments/7')

    await screen.findByText('Glucides nets')
    expect(screen.getByText('7,3')).toBeInTheDocument()
  })

  it('ne propose pas de modifier une fiche Ciqual', async () => {
    stubDetail()
    renderRoute('/aliments/7')

    await screen.findByRole('heading', { name: 'Abricot, dénoyauté, cru' })
    expect(screen.queryByRole('link', { name: /Modifier cet aliment/ })).not.toBeInTheDocument()
  })

  it('propose de modifier son propre aliment', async () => {
    stubDetail(
      detail({ is_editable: true, is_own: true, source: 'user', source_label: 'Utilisateur' }),
    )
    renderRoute('/aliments/7')

    expect(await screen.findByRole('link', { name: /Modifier cet aliment/ })).toBeInTheDocument()
  })

  it('permet de basculer le favori', async () => {
    const user = userEvent.setup()
    const spy = stubDetail()
    renderRoute('/aliments/7')

    await user.click(await screen.findByRole('button', { name: 'Ajouter aux favoris' }))

    await waitFor(() => {
      const calls = spy.mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/foods/7/favorite/'))).toBe(true)
    })
  })

  it('affiche les portions et signale celles qui sont personnelles', async () => {
    stubDetail(
      detail({
        portions: [
          {
            id: 1,
            name: '1 tranche',
            gram_equivalent: '32.000',
            milliliter_equivalent: null,
            unit_equivalent: null,
            is_default: false,
            sort_order: 0,
            is_own: true,
          },
        ],
      }),
    )
    renderRoute('/aliments/7')

    expect(await screen.findByText('1 tranche')).toBeInTheDocument()
    expect(screen.getByText(/portion personnelle/)).toBeInTheDocument()
  })

  it('signale une fiche introuvable', async () => {
    stubFetch([
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      {
        match: '/foods/7/',
        respond: () =>
          jsonResponse({ code: 'not_found', message: 'Ressource introuvable.', errors: {} }, 404),
      },
    ])
    renderRoute('/aliments/7')

    expect(await screen.findByRole('alert')).toHaveTextContent('Ressource introuvable.')
  })
})
