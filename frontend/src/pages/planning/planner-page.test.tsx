import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MacroValues, MealPlanTask, PlanProposal } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const TASK_ID = '7f2504e0-4f89-11d3-9a0c-0305e82c3301'

const VALUES: MacroValues = {
  energy_kcal: '1900.000',
  protein_g: '95.000',
  carbohydrates_g: '190.000',
  fat_g: '65.000',
}

function proposal(overrides: Partial<PlanProposal> = {}): PlanProposal {
  return {
    name: 'Semaine du 31/08',
    start_date: '2026-08-31',
    end_date: '2026-08-31',
    warnings: [],
    days: [
      {
        date: '2026-08-31',
        targets: { daily_calories: '2000' },
        totals: VALUES,
        deviations: { daily_calories: -5 },
        within_tolerance: true,
        attempts: 1,
        unmatched: [],
        meals: [
          {
            meal: 'Petit-déjeuner',
            meal_type_id: 1,
            items: [
              {
                entry_type: 'food',
                label: 'Flocons d’avoine',
                quantity: '60',
                unit_label: 'g',
                values: { ...VALUES, energy_kcal: '220.000' },
              },
            ],
          },
        ],
      },
    ],
    ...overrides,
  }
}

function task(result: PlanProposal | null = proposal(), overrides: Partial<MealPlanTask> = {}) {
  return {
    id: TASK_ID,
    task_type: 'meal_planner' as const,
    status: 'success' as const,
    progress: 100,
    result,
    error: null,
    created_at: '2026-08-28T12:00:00Z',
    ...overrides,
  }
}

function stubPlanner(payload = task(), enabled = true) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/ai/status/', respond: () => jsonResponse({ enabled }) },
      { match: '/meal-plans/generate/', respond: () => jsonResponse(payload, 202) },
      { match: `/tasks/${TASK_ID}/`, respond: () => jsonResponse(payload) },
      { match: '/meal-plans/', respond: () => jsonResponse({ id: 3, name: 'Semaine du 31/08' }) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function sent(spy: ReturnType<typeof stubFetch>, path: string, method: string) {
  return spy.mock.calls.filter(
    ([url, init]) => String(url).includes(path) && init?.method === method,
  )
}

async function compose(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Composer le plan' }))
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('planner', () => {
  it('affiche les totaux recalculés et l’écart mesuré', async () => {
    const user = userEvent.setup()
    stubPlanner()
    renderRoute('/planification')

    await compose(user)

    expect(await screen.findByText('Proposition')).toBeInTheDocument()
    expect(screen.getByText('1 900')).toBeInTheDocument()
    expect(screen.getByText('-5 %')).toBeInTheDocument()
  })

  it('n’enregistre rien tant que l’utilisateur n’a pas validé', async () => {
    const user = userEvent.setup()
    const spy = stubPlanner()
    renderRoute('/planification')

    await compose(user)
    await screen.findByText('Proposition')

    expect(
      sent(spy, '/meal-plans/', 'POST').filter(([url]) => !String(url).includes('generate')),
    ).toHaveLength(0)
  })

  it('enregistre le planning relu', async () => {
    const user = userEvent.setup()
    const spy = stubPlanner()
    renderRoute('/planification')

    await compose(user)
    await user.click(await screen.findByRole('button', { name: 'Enregistrer cette planification' }))

    await waitFor(() =>
      expect(
        sent(spy, '/meal-plans/', 'POST').filter(([url]) => !String(url).includes('generate')),
      ).toHaveLength(1),
    )
  })

  it('nomme les recettes qui seront créées, avant de les créer', async () => {
    const user = userEvent.setup()
    const avecRecette = proposal()
    avecRecette.days[0]!.meals[0]!.items.push({
      entry_type: 'recipe',
      label: 'Poêlée du soir',
      quantity: '1',
      unit_label: 'portion',
      values: VALUES,
      new_recipe: { name: 'Poêlée du soir', servings: '2', instructions: '', ingredients: [] },
    })
    stubPlanner(task(avecRecette))
    renderRoute('/planification')

    await compose(user)

    expect(
      await screen.findByText(/Une recette sera ajoutée à vos recettes : Poêlée du soir/),
    ).toBeInTheDocument()
  })

  it('signale une journée restée hors tolérance', async () => {
    const user = userEvent.setup()
    const rate = proposal({ warnings: ['Le 31/08 reste à 18 % de l’objectif après 3 essais.'] })
    stubPlanner(task(rate))
    renderRoute('/planification')

    await compose(user)

    expect(await screen.findByText(/reste à 18 %/)).toBeInTheDocument()
  })

  it('annonce l’indisponibilité de l’IA dès l’ouverture', async () => {
    stubPlanner(task(), false)
    renderRoute('/planification')

    expect(await screen.findByText(/L’analyse par IA est indisponible/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Composer le plan' })).not.toBeInTheDocument()
  })

  it('affiche l’échec et propose de recommencer', async () => {
    const user = userEvent.setup()
    stubPlanner(task(null, { status: 'failed', error: 'Aucun objectif nutritionnel.' }))
    renderRoute('/planification')

    await compose(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Aucun objectif')
  })
})
