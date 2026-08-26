import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DiaryDay, MealType, NutritionValues } from '@/lib/api/types'
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

const MEALS: MealType[] = [
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

const NUTRIENTS = [
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

function nutrition(values: Partial<NutritionValues> = {}): NutritionValues {
  return Object.fromEntries(
    NUTRIENTS.map((key) => [key, values[key] ?? null]),
  ) as unknown as NutritionValues
}

const ENTRY = {
  id: 10,
  meal_type_id: 1,
  entry_type: 'food' as const,
  consumed_at: '2026-08-26T08:00:00Z',
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
}

function day(): DiaryDay {
  return {
    date: '2026-08-26',
    notes: '',
    goals: null,
    totals: nutrition({ energy_kcal: '288.000' }),
    incomplete_nutrients: [],
    remaining: null,
    meals: [
      {
        meal_type: MEALS[0]!,
        entries: [ENTRY],
        totals: nutrition({ energy_kcal: '288.000' }),
        incomplete_nutrients: [],
      },
      {
        meal_type: MEALS[1]!,
        entries: [],
        totals: nutrition({ energy_kcal: '0.000' }),
        incomplete_nutrients: [],
      },
    ],
  }
}

interface Calls {
  duplicate?: () => void
  copyDay?: (body: string) => void
  copyMeal?: () => void
  patch?: (body: string) => void
}

function stubJournal(calls: Calls = {}) {
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
        match: '/duplicate/',
        respond: () => {
          calls.duplicate?.()
          return jsonResponse(ENTRY, 201)
        },
      },
      {
        match: '/diary/copy-day/',
        respond: () => {
          calls.copyDay?.('')
          return jsonResponse([ENTRY], 201)
        },
      },
      {
        match: '/diary/copy-meal/',
        respond: () => {
          calls.copyMeal?.()
          return jsonResponse([ENTRY], 201)
        },
      },
      {
        match: '/diary/entries/',
        respond: () => {
          calls.patch?.('')
          return jsonResponse(ENTRY)
        },
      },
      { match: '/diary/', respond: () => jsonResponse(day()) },
    ],
    () => jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
}

/** Panneau de copie portant ce titre.
 *
 * Le bouton « Ajouter » du sélecteur de dates porte le même nom que le `+` de
 * la barre de navigation : il faut cibler le panneau.
 */
async function copyPanel(title: RegExp) {
  const heading = await screen.findByText(title)
  return within(heading.closest('[data-slot="card"]') as HTMLElement)
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Copie et déplacement', () => {
  it('duplique une entrée', async () => {
    const user = userEvent.setup()
    const duplicate = vi.fn()
    stubJournal({ duplicate })
    renderRoute('/journal?date=2026-08-26')

    await user.click(await screen.findByRole('button', { name: 'Dupliquer Poulet rôti' }))

    await waitFor(() => expect(duplicate).toHaveBeenCalled())
  })

  it('déplace une entrée vers un autre repas', async () => {
    const user = userEvent.setup()
    const patch = vi.fn()
    stubJournal({ patch })
    renderRoute('/journal?date=2026-08-26')

    await user.click(await screen.findByRole('button', { name: 'Déplacer Poulet rôti' }))
    // Seuls les autres repas sont proposés.
    await user.click(await screen.findByRole('button', { name: 'Déjeuner' }))

    await waitFor(() => expect(patch).toHaveBeenCalled())
  })

  it('exige au moins une date avant de copier', async () => {
    const user = userEvent.setup()
    stubJournal()
    renderRoute('/journal?date=2026-08-26')

    await user.click(await screen.findByRole('button', { name: /Copier la journée/ }))

    expect(await screen.findByText('Aucune date choisie.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copier' })).toBeDisabled()
  })

  it('copie la journée vers les dates choisies', async () => {
    const user = userEvent.setup()
    const copyDay = vi.fn()
    stubJournal({ copyDay })
    renderRoute('/journal?date=2026-08-26')

    await user.click(await screen.findByRole('button', { name: /Copier la journée/ }))
    const panel = await copyPanel(/Copier cette journée/)
    await user.click(panel.getByRole('button', { name: 'Ajouter' }))
    await user.click(panel.getByRole('button', { name: 'Copier' }))

    await waitFor(() => expect(copyDay).toHaveBeenCalled())
  })

  it('permet de retirer une date choisie', async () => {
    const user = userEvent.setup()
    stubJournal()
    renderRoute('/journal?date=2026-08-26')

    await user.click(await screen.findByRole('button', { name: /Copier la journée/ }))
    const panel = await copyPanel(/Copier cette journée/)
    await user.click(panel.getByRole('button', { name: 'Ajouter' }))
    await user.click(panel.getByRole('button', { name: /^Retirer le / }))

    expect(await screen.findByText('Aucune date choisie.')).toBeInTheDocument()
  })

  it('copie un repas depuis sa carte', async () => {
    const user = userEvent.setup()
    const copyMeal = vi.fn()
    stubJournal({ copyMeal })
    renderRoute('/journal?date=2026-08-26')

    await user.click(await screen.findByRole('button', { name: /Copier ce repas/ }))
    const panel = await copyPanel(/Copier « Petit-déjeuner »/)
    await user.click(panel.getByRole('button', { name: 'Ajouter' }))
    await user.click(panel.getByRole('button', { name: 'Copier' }))

    await waitFor(() => expect(copyMeal).toHaveBeenCalled())
  })

  it('n’offre pas de copier un repas vide', async () => {
    stubJournal()
    renderRoute('/journal?date=2026-08-26')

    await screen.findByRole('heading', { name: 'Déjeuner' })

    // Un seul repas contient des entrées.
    expect(screen.getAllByRole('button', { name: /Copier ce repas/ })).toHaveLength(1)
  })
})
