import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SavedMeal } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated, savedMeal } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function stubSavedMeals(
  meals: SavedMeal[] = [savedMeal()],
  addResult: () => Response = () => jsonResponse({ entries: [{ id: 1 }], skipped: [] }, 201),
) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/add-to-diary/', respond: addResult },
      { match: '/saved-meals/', respond: () => jsonResponse(paginated(meals)) },
    ],
    () => jsonResponse(paginated([])),
  )
}

/** Carte d'un repas, une fois la liste chargée. */
async function mealCard(name: string): Promise<HTMLElement> {
  const heading = await screen.findByRole('heading', { name })
  return heading.closest('[data-slot="card"]') as HTMLElement
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Repas enregistrés', () => {
  it('affiche les repas et leurs éléments', async () => {
    stubSavedMeals()
    renderRoute('/mes-repas')

    expect(await screen.findByRole('heading', { name: 'Mes repas' })).toBeInTheDocument()
    const card = within(await mealCard('Mon déjeuner'))
    expect(card.getByText('Poulet')).toBeInTheDocument()
    expect(card.getByText(/150/)).toBeInTheDocument()
  })

  it('invite à en créer un quand il n’y en a aucun', async () => {
    stubSavedMeals([])
    renderRoute('/mes-repas')

    expect(await screen.findByText('Aucun repas enregistré')).toBeInTheDocument()
  })

  it('ajoute un repas au journal', async () => {
    const user = userEvent.setup()
    const spy = stubSavedMeals()
    renderRoute('/mes-repas')

    const card = within(await mealCard('Mon déjeuner'))
    await user.click(await card.findByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() =>
      expect(
        spy.mock.calls.find(
          ([url, init]) => String(url).includes('/add-to-diary/') && init?.method === 'POST',
        ),
      ).toBeDefined(),
    )
  })

  it('signale les éléments dont la source a disparu', async () => {
    stubSavedMeals([
      savedMeal({
        items: [
          {
            id: 1,
            item_type: 'food',
            food: null,
            recipe: null,
            item_name: 'Poulet',
            quantity: '150.000',
            unit_label: 'g',
            sort_order: 0,
          },
        ],
      }),
    ])
    renderRoute('/mes-repas')

    expect(await screen.findByText('source supprimée')).toBeInTheDocument()
  })

  it('exige un nom et au moins un élément', async () => {
    stubSavedMeals([])
    renderRoute('/mes-repas')

    const form = (await screen.findByLabelText('Nom')).closest('form') as HTMLElement
    expect(within(form).getByRole('button', { name: 'Enregistrer le repas' })).toBeDisabled()
  })
})
