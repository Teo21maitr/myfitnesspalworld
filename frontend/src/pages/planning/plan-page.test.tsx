import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MacroValues, MealPlan } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const VALUES: MacroValues = {
  energy_kcal: '1900.000',
  protein_g: '95.000',
  carbohydrates_g: '190.000',
  fat_g: '65.000',
}

const PLAN: MealPlan = {
  id: 3,
  name: 'Semaine du 31/08',
  start_date: '2026-08-31',
  end_date: '2026-08-31',
  generated_by_ai: true,
  days_count: 1,
  created_at: '2026-08-28T12:00:00Z',
  notes: '',
  days: [
    {
      id: 9,
      date: '2026-08-31',
      entries: [
        {
          id: 1,
          meal_type: 1,
          entry_type: 'food',
          food: 5,
          recipe: null,
          quantity: '60',
          unit_label: 'g',
          sort_order: 0,
          generated_by_ai: true,
          label: 'Flocons d’avoine',
          values: { ...VALUES, energy_kcal: '220.000' },
        },
      ],
      totals: VALUES,
      incomplete_nutrients: [],
      targets: { daily_calories: '2000' },
      deviations: { daily_calories: -5 },
      within_tolerance: true,
    },
  ],
}

function stubPlan(conflicts: string[] = []) {
  let confirmed = false

  return stubFetch(
    [
      ...BASE_ROUTES,
      {
        match: '/meal-plans/3/add-to-diary/',
        respond: () => {
          const body =
            confirmed || conflicts.length === 0
              ? { entries: [{ id: 1 }], skipped: [], conflicts }
              : { entries: [], skipped: [], conflicts }
          confirmed = true
          return jsonResponse(body, 201)
        },
      },
      { match: '/meal-plans/3/', respond: () => jsonResponse(PLAN) },
      { match: '/shopping-lists/generate/', respond: () => jsonResponse({ id: 8 }, 201) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function sent(spy: ReturnType<typeof stubFetch>, path: string) {
  return spy.mock.calls.filter(
    ([url, init]) => String(url).includes(path) && init?.method === 'POST',
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('planning enregistré', () => {
  it('affiche la journée et son écart', async () => {
    stubPlan()
    renderRoute('/planification/3')

    expect(await screen.findByRole('heading', { name: 'Semaine du 31/08' })).toBeInTheDocument()
    expect(screen.getByText('Flocons d’avoine')).toBeInTheDocument()
    expect(screen.getByText('-5 %')).toBeInTheDocument()
  })

  it('demande confirmation quand un repas contient déjà quelque chose', async () => {
    // Rien n'est écrit tant que l'utilisateur n'a pas confirmé (spec 01 §15).
    const user = userEvent.setup()
    stubPlan(['31/08 — Petit-déjeuner'])
    renderRoute('/planification/3')

    await user.click(await screen.findByRole('button', { name: 'Ajouter au journal' }))

    expect(await screen.findByText('Ces repas contiennent déjà quelque chose')).toBeInTheDocument()
    expect(screen.getByText('31/08 — Petit-déjeuner')).toBeInTheDocument()
  })

  it('rappelle que rien ne sera remplacé', async () => {
    const user = userEvent.setup()
    stubPlan(['31/08 — Petit-déjeuner'])
    renderRoute('/planification/3')

    await user.click(await screen.findByRole('button', { name: 'Ajouter au journal' }))

    expect(await screen.findByText(/Rien ne sera remplacé/)).toBeInTheDocument()
  })

  it('ajoute après confirmation', async () => {
    const user = userEvent.setup()
    const spy = stubPlan(['31/08 — Petit-déjeuner'])
    renderRoute('/planification/3')

    await user.click(await screen.findByRole('button', { name: 'Ajouter au journal' }))
    await user.click(await screen.findByRole('button', { name: 'Ajouter quand même' }))

    await waitFor(() => expect(sent(spy, '/add-to-diary/')).toHaveLength(2))
    const body = JSON.parse(String(sent(spy, '/add-to-diary/')[1]?.[1]?.body))
    expect(body.confirm).toBe(true)
  })

  it('ajoute sans confirmation quand rien n’est en travers', async () => {
    const user = userEvent.setup()
    const spy = stubPlan()
    renderRoute('/planification/3')

    await user.click(await screen.findByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => expect(sent(spy, '/add-to-diary/')).toHaveLength(1))
    expect(screen.queryByText('Ces repas contiennent déjà quelque chose')).not.toBeInTheDocument()
  })

  it('tire la liste de courses du planning', async () => {
    const user = userEvent.setup()
    const spy = stubPlan()
    renderRoute('/planification/3')

    await user.click(await screen.findByRole('button', { name: 'Liste de courses' }))

    await waitFor(() => expect(sent(spy, '/shopping-lists/generate/')).toHaveLength(1))
    const body = JSON.parse(String(sent(spy, '/shopping-lists/generate/')[0]?.[1]?.body))
    expect(body.meal_plan_id).toBe(3)
  })
})
