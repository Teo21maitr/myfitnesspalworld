import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DiaryDay, NutritionValues } from '@/lib/api/types'
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

/** Toutes les valeurs inconnues, sauf celles qu'on précise. */
function nutrition(values: Partial<NutritionValues> = {}): NutritionValues {
  const keys = [
    'energy_kcal',
    'protein_g',
    'carbohydrates_g',
    'fat_g',
    'fiber_g',
    'sugars_g',
    'sodium_mg',
    'salt_g',
    'cholesterol_mg',
    'potassium_mg',
    'calcium_mg',
    'iron_mg',
    'magnesium_mg',
    'vitamin_a_ug',
    'vitamin_b6_mg',
    'vitamin_b12_ug',
    'vitamin_c_mg',
    'vitamin_d_ug',
    'vitamin_e_mg',
    'vitamin_k_ug',
  ] as const

  return Object.fromEntries(
    keys.map((key) => [key, values[key] ?? null]),
  ) as unknown as NutritionValues
}

function entry(overrides: Record<string, unknown> = {}) {
  return {
    id: 10,
    meal_type_id: 1,
    entry_type: 'food' as const,
    consumed_at: '2026-08-25T08:00:00Z',
    quantity: '150.000',
    unit_label: 'g',
    note: '',
    food: 7,
    snapshot_name: 'Poulet rôti',
    snapshot_brand: '',
    snapshot_source: 'ciqual',
    snapshot_reference_amount: '100.000',
    snapshot_reference_unit: 'g' as const,
    computed: nutrition({ energy_kcal: '288.000' }),
    ...overrides,
  }
}

function day(overrides: Partial<DiaryDay> = {}): DiaryDay {
  return {
    date: '2026-08-25',
    notes: '',
    goals: {
      date: '2026-08-25',
      weekday: 1,
      daily_calories: '2000.00',
      protein_g: '150.00',
      carbs_g: '200.00',
      fat_g: '67.00',
      fiber_g: null,
    },
    totals: nutrition({ energy_kcal: '288.000', protein_g: '25.950' }),
    incomplete_nutrients: [],
    remaining: {
      daily_calories: '1712.00',
      protein_g: '124.05',
      carbs_g: '200.00',
      fat_g: '67.00',
      fiber_g: null,
    },
    meals: [
      {
        meal_type: MEAL,
        entries: [entry()],
        totals: nutrition({ energy_kcal: '288.000' }),
        incomplete_nutrients: [],
      },
    ],
    ...overrides,
  }
}

interface StubOptions {
  diary?: () => Response
  onPatch?: (body: string) => void
  onDelete?: () => void
}

function stubDiary({ diary, onPatch, onDelete }: StubOptions = {}) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/meal-types/', respond: () => jsonResponse([MEAL]) },
      {
        match: '/diary/entries/',
        respond: () => {
          onPatch?.('')
          onDelete?.()
          return jsonResponse(entry())
        },
      },
      { match: '/diary/', respond: () => (diary ? diary() : jsonResponse(day())) },
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

describe('Journal', () => {
  it('affiche les repas, les totaux et l’objectif du jour', async () => {
    stubDiary()
    renderRoute('/journal?date=2026-08-25')

    expect(await screen.findByRole('heading', { name: 'Journal' })).toBeInTheDocument()
    expect(await screen.findByText('Petit-déjeuner')).toBeInTheDocument()
    expect(screen.getByText('Poulet rôti')).toBeInTheDocument()
    expect(screen.getAllByText('288').length).toBeGreaterThan(0)
    expect(screen.getByText('2 000')).toBeInTheDocument()
  })

  it('signale une journée sans objectif', async () => {
    stubDiary({ diary: () => jsonResponse(day({ goals: null, remaining: null })) })
    renderRoute('/journal?date=2026-08-25')

    expect(await screen.findByText(/Aucun objectif défini/)).toBeInTheDocument()
  })

  it('signale un repas vide', async () => {
    stubDiary({
      diary: () =>
        jsonResponse(
          day({
            meals: [
              {
                meal_type: MEAL,
                entries: [],
                totals: nutrition(),
                incomplete_nutrients: [],
              },
            ],
          }),
        ),
    })
    renderRoute('/journal?date=2026-08-25')

    expect(await screen.findByText('Rien pour l’instant.')).toBeInTheDocument()
  })

  it('signale un total partiel plutôt que de le présenter comme exact', async () => {
    stubDiary({
      diary: () => jsonResponse(day({ incomplete_nutrients: ['fiber_g'] })),
    })
    renderRoute('/journal?date=2026-08-25')

    expect(await screen.findByText(/totaux marqués sont partiels/)).toBeInTheDocument()
  })

  it('navigue d’un jour à l’autre', async () => {
    const user = userEvent.setup()
    stubDiary()
    const { router } = renderRoute('/journal?date=2026-08-25')

    await user.click(await screen.findByRole('button', { name: 'Jour précédent' }))

    await waitFor(() => {
      expect(router.state.location.search).toContain('date=2026-08-24')
    })
  })

  it('permet de modifier la quantité d’une entrée', async () => {
    const user = userEvent.setup()
    const onPatch = vi.fn()
    stubDiary({ onPatch })
    renderRoute('/journal?date=2026-08-25')

    await user.click(await screen.findByRole('button', { name: 'Modifier Poulet rôti' }))
    const field = screen.getByRole('textbox', { name: 'Quantité de Poulet rôti' })
    await user.clear(field)
    await user.type(field, '300')
    await user.click(screen.getByRole('button', { name: 'Valider' }))

    await waitFor(() => expect(onPatch).toHaveBeenCalled())
  })

  it('permet de supprimer une entrée', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    stubDiary({ onDelete })
    renderRoute('/journal?date=2026-08-25')

    await user.click(await screen.findByRole('button', { name: 'Supprimer Poulet rôti' }))

    await waitFor(() => expect(onDelete).toHaveBeenCalled())
  })

  it('affiche l’erreur quand le journal est inaccessible', async () => {
    stubDiary({
      diary: () =>
        jsonResponse({ code: 'error', message: 'Service indisponible.', errors: {} }, 500),
    })
    renderRoute('/journal?date=2026-08-25')

    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible.')
  })
})
