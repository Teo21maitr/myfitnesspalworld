import { describe, expect, it } from 'vitest'

import type { MacroValues, PlanDay, ProposalDay } from '@/lib/api/types'

import { toPayload } from './api'
import { fromPlan, fromProposal } from './day-view'

const VALUES: MacroValues = {
  energy_kcal: '300.000',
  protein_g: '20.000',
  carbohydrates_g: '10.000',
  fat_g: '5.000',
}

function proposalDay(overrides: Partial<ProposalDay> = {}): ProposalDay {
  return {
    date: '2026-08-31',
    targets: { daily_calories: '2000' },
    totals: VALUES,
    deviations: { daily_calories: -85 },
    within_tolerance: false,
    attempts: 3,
    unmatched: ['zorglub'],
    meals: [
      {
        meal: 'Déjeuner',
        meal_type_id: 2,
        items: [
          {
            entry_type: 'food',
            label: 'Poulet',
            quantity: '150',
            unit_label: 'g',
            values: VALUES,
            food: undefined,
          },
        ],
      },
    ],
    ...overrides,
  }
}

describe('journée proposée', () => {
  it('signale une recette qui n’existe pas encore', () => {
    const day = proposalDay({
      meals: [
        {
          meal: 'Dîner',
          meal_type_id: 3,
          items: [
            {
              entry_type: 'recipe',
              label: 'Poêlée du soir',
              quantity: '1',
              unit_label: 'portion',
              values: VALUES,
              new_recipe: {
                name: 'Poêlée du soir',
                servings: '2',
                instructions: '',
                ingredients: [],
              },
            },
          ],
        },
      ],
    })

    expect(fromProposal(day).meals[0]?.items[0]?.isNewRecipe).toBe(true)
  })

  it('reporte les libellés que la base n’a pas retrouvés', () => {
    expect(fromProposal(proposalDay()).unmatched).toEqual(['zorglub'])
  })
})

describe('journée enregistrée', () => {
  const day: PlanDay = {
    id: 7,
    date: '2026-08-31',
    entries: [
      {
        id: 1,
        meal_type: 2,
        entry_type: 'food',
        food: 5,
        recipe: null,
        quantity: '150',
        unit_label: 'g',
        sort_order: 0,
        generated_by_ai: true,
        label: 'Poulet',
        values: VALUES,
      },
    ],
    totals: VALUES,
    incomplete_nutrients: [],
    targets: { daily_calories: '2000' },
    deviations: { daily_calories: -85 },
    within_tolerance: false,
  }

  it('regroupe les entrées par repas, dans l’ordre de l’utilisateur', () => {
    const view = fromPlan(day, [
      { id: 1, name: 'Petit-déjeuner' },
      { id: 2, name: 'Déjeuner' },
    ])

    // Les repas vides ne sont pas affichés.
    expect(view.meals).toHaveLength(1)
    expect(view.meals[0]?.meal).toBe('Déjeuner')
  })
})

describe('proposition envoyée à l’enregistrement', () => {
  it('conserve les recettes inédites, que le serveur créera', () => {
    const day = proposalDay({
      meals: [
        {
          meal: 'Dîner',
          meal_type_id: 3,
          items: [
            {
              entry_type: 'recipe',
              label: 'Poêlée',
              quantity: '1',
              unit_label: 'portion',
              values: VALUES,
              new_recipe: {
                name: 'Poêlée',
                servings: '2',
                instructions: 'Cuire.',
                ingredients: [{ food_id: 5, label: 'Poulet', quantity: '300', unit_label: 'g' }],
              },
            },
          ],
        },
      ],
    })

    const payload = toPayload(
      {
        name: 'Semaine',
        start_date: '2026-08-31',
        end_date: '2026-08-31',
        days: [day],
        warnings: [],
      },
      [day],
    )

    expect(payload.days[0]?.entries[0]?.new_recipe?.name).toBe('Poêlée')
    expect(payload.generated_by_ai).toBe(true)
  })

  it('écarte un repas que le compte ne connaît pas', () => {
    const day = proposalDay({
      meals: [{ meal: 'Inconnu', meal_type_id: null, items: [] }],
    })

    const payload = toPayload(
      {
        name: 'Semaine',
        start_date: '2026-08-31',
        end_date: '2026-08-31',
        days: [day],
        warnings: [],
      },
      [day],
    )

    expect(payload.days[0]?.entries).toEqual([])
  })
})
