import { screen, waitFor, within } from '@testing-library/react'
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

const MEALS = [
  {
    id: 1,
    name: 'Petit-déjeuner',
    slug: 'petit-dejeuner',
    sort_order: 0,
    is_active: true,
    is_system: true,
    system_key: 'breakfast',
  },
  {
    id: 2,
    name: 'Déjeuner',
    slug: 'dejeuner',
    sort_order: 1,
    is_active: true,
    is_system: true,
    system_key: 'lunch',
  },
]

function food(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
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
    barcode: null,
    visibility: 'private',
    default_unit_type: 'g',
    nutrition: {
      energy_kcal: '192.000',
      protein_g: '17.300',
      carbohydrates_g: null,
      fat_g: '13.500',
      fiber_g: null,
      net_carbs_g: null,
      sugars_g: null,
      sodium_mg: null,
      salt_g: null,
      cholesterol_mg: null,
      potassium_mg: null,
      calcium_mg: null,
      iron_mg: null,
      magnesium_mg: null,
      vitamin_a_ug: null,
      vitamin_b6_mg: null,
      vitamin_b12_ug: null,
      vitamin_c_mg: null,
      vitamin_d_ug: null,
      vitamin_e_mg: null,
      vitamin_k_ug: null,
    },
    portions: [],
    available_units: ['g', 'kg'],
    is_editable: false,
    created_at: '2026-08-25T10:00:00Z',
    updated_at: '2026-08-25T10:00:00Z',
    ...overrides,
  }
}

function stubFood(detail = food(), onCreate?: (body: string) => void) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/meal-types/', respond: () => jsonResponse(MEALS) },
      {
        match: '/diary/entries/',
        respond: () => {
          onCreate?.('')
          return jsonResponse({ id: 1 }, 201)
        },
      },
      { match: '/foods/7/', respond: () => jsonResponse(detail) },
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

describe('Ajout au journal', () => {
  it('ne propose que les unités calculables pour l’aliment', async () => {
    stubFood()
    renderRoute('/aliments/7')

    const unit = await screen.findByLabelText('Unité')
    const options = Array.from(unit.querySelectorAll('option')).map((node) => node.textContent)

    // Une cuillère est une mesure de volume : jamais proposée sur un solide
    // (spec 01 §9).
    expect(options).toEqual(['g', 'kg'])
  })

  it('recalcule les valeurs à la frappe', async () => {
    const user = userEvent.setup()
    stubFood()
    renderRoute('/aliments/7')

    const quantity = await screen.findByLabelText('Quantité')
    await user.clear(quantity)
    await user.type(quantity, '200')

    const apercu = screen.getByLabelText('Aperçu des valeurs')
    // 192 kcal pour 100 g, donc 384 pour 200 g.
    expect(await within(apercu).findByText('384')).toBeInTheDocument()
  })

  it('laisse « — » sur un nutriment inconnu', async () => {
    stubFood()
    renderRoute('/aliments/7')

    const apercu = await screen.findByLabelText('Aperçu des valeurs')
    // Les glucides ne sont pas renseignés : ils ne valent pas zéro.
    expect(within(apercu).getByText('—')).toBeInTheDocument()
  })

  it('envoie l’ajout au journal', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn()
    stubFood(food(), onCreate)
    renderRoute('/aliments/7')

    await user.click(await screen.findByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => expect(onCreate).toHaveBeenCalled())
  })

  it('invite à créer une portion quand aucune unité n’est utilisable', async () => {
    stubFood(food({ available_units: [] }))
    renderRoute('/aliments/7')

    expect(await screen.findByText(/aucune unité utilisable/)).toBeInTheDocument()
  })
})
