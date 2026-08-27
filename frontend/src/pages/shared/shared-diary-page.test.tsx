import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DiaryDay, NutritionValues } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, MEAL_TYPES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

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

function day(): DiaryDay {
  return {
    date: '2026-08-26',
    notes: '',
    goals: null,
    totals: nutrition({ energy_kcal: '400.000' }),
    incomplete_nutrients: [],
    remaining: null,
    meals: [
      {
        meal_type: MEAL_TYPES[0]!,
        entries: [
          {
            id: 10,
            meal_type_id: 1,
            entry_type: 'food',
            consumed_at: '2026-08-26T12:00:00Z',
            quantity: '200.000',
            unit_label: 'g',
            note: '',
            food: 7,
            snapshot_name: 'Poulet',
            snapshot_brand: '',
            snapshot_source: 'ciqual',
            snapshot_reference_amount: '100.000',
            snapshot_reference_unit: 'g',
            computed: nutrition({ energy_kcal: '400.000' }),
          },
        ],
        totals: nutrition({ energy_kcal: '400.000' }),
        incomplete_nutrients: [],
      },
    ],
  }
}

function stubShared(respond: () => Response = () => jsonResponse(day())) {
  return stubFetch([...BASE_ROUTES, { match: '/shared/diary/', respond }], () =>
    jsonResponse(paginated([])),
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Journal partagé', () => {
  it('affiche la journée d’un ami', async () => {
    stubShared()
    renderRoute('/amis/2/journal')

    expect(await screen.findByRole('heading', { name: 'Journal partagé' })).toBeInTheDocument()
    expect(await screen.findByText('Poulet')).toBeInTheDocument()
    expect(screen.getByText('Consultation seule.')).toBeInTheDocument()
  })

  it('n’offre aucune action d’écriture', async () => {
    // Le backend refuserait, mais proposer une action vouée au refus est déjà
    // un défaut (spec 05 §8).
    stubShared()
    renderRoute('/amis/2/journal')

    await screen.findByText('Poulet')

    // Le contenu de la page, sans la barre de navigation qui porte son propre
    // bouton « Ajouter ».
    const page = within(screen.getByRole('main'))
    for (const forbidden of [/^Modifier/, /^Supprimer/, /^Dupliquer/, /^Déplacer/, /^Ajouter/]) {
      expect(page.queryByRole('button', { name: forbidden })).not.toBeInTheDocument()
    }
  })

  it('permet de changer de jour', async () => {
    stubShared()
    renderRoute('/amis/2/journal')

    expect(await screen.findByRole('button', { name: 'Jour précédent' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jour suivant' })).toBeInTheDocument()
  })

  it('affiche un message lisible quand le partage n’existe pas', async () => {
    stubShared(() =>
      jsonResponse({ code: 'not_found', message: 'Contenu introuvable.', errors: {} }, 404),
    )
    renderRoute('/amis/2/journal')

    expect(await screen.findByRole('alert')).toHaveTextContent('Contenu introuvable.')
  })
})
