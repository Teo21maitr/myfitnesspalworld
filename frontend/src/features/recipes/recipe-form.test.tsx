import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const CHICKEN = {
  id: 7,
  name: 'Poulet rôti',
  brand: '',
  source: 'ciqual',
  source_label: 'Ciqual',
  reference_amount: '100.000',
  reference_unit: 'g',
  energy_kcal: '192.000',
  is_favorite: false,
  is_own: false,
  is_verified: true,
}

const CHICKEN_DETAIL = {
  ...CHICKEN,
  barcode: null,
  visibility: 'private',
  default_unit_type: 'g',
  nutrition: null,
  portions: [],
  // Seules les unités calculables sont proposées (spec 01 §9).
  available_units: ['g', 'kg'],
  is_editable: false,
  created_at: '2026-08-26T08:00:00Z',
  updated_at: '2026-08-26T08:00:00Z',
}

function stubCreation(onCreate?: (body: string) => void) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/foods/search/', respond: () => jsonResponse(paginated([CHICKEN])) },
      { match: '/foods/7/', respond: () => jsonResponse(CHICKEN_DETAIL) },
      {
        match: '/recipes/',
        respond: () => {
          onCreate?.('')
          return jsonResponse({ id: 3 }, 201)
        },
      },
    ],
    () => jsonResponse(paginated([])),
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Composition d’une recette', () => {
  it('exige un nom avant d’enregistrer', async () => {
    stubCreation()
    renderRoute('/recettes/nouvelle')

    expect(await screen.findByRole('button', { name: 'Créer la recette' })).toBeDisabled()
  })

  it('refuse un nombre de portions nul', async () => {
    const user = userEvent.setup()
    stubCreation()
    renderRoute('/recettes/nouvelle')

    await user.type(await screen.findByLabelText('Nom'), 'Poulet riz')
    await user.clear(screen.getByLabelText('Portions'))
    await user.type(screen.getByLabelText('Portions'), '0')

    expect(screen.getByRole('button', { name: 'Créer la recette' })).toBeDisabled()
  })

  it('ajoute un ingrédient trouvé par la recherche', async () => {
    const user = userEvent.setup()
    stubCreation()
    renderRoute('/recettes/nouvelle')

    await user.type(await screen.findByLabelText('Chercher un ingrédient'), 'poulet')
    await user.click(await screen.findByRole('button', { name: /Poulet rôti/ }))

    // Le choix fait, la quantité et l'unité s'ajustent.
    const quantity = await screen.findByLabelText('Quantité')
    await user.clear(quantity)
    await user.type(quantity, '200')
    await user.click(screen.getByRole('button', { name: 'Ajouter Poulet rôti' }))

    expect(await screen.findByText('Poulet rôti')).toBeInTheDocument()
    expect(screen.getByText('200 g')).toBeInTheDocument()
  })

  it('ne propose que les unités calculables', async () => {
    const user = userEvent.setup()
    stubCreation()
    renderRoute('/recettes/nouvelle')

    await user.type(await screen.findByLabelText('Chercher un ingrédient'), 'poulet')
    await user.click(await screen.findByRole('button', { name: /Poulet rôti/ }))

    const unit = await screen.findByLabelText('Unité')
    const options = within(unit)
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(options).toEqual(['g', 'kg'])
  })

  it('retire un ingrédient ajouté', async () => {
    const user = userEvent.setup()
    stubCreation()
    renderRoute('/recettes/nouvelle')

    await user.type(await screen.findByLabelText('Chercher un ingrédient'), 'poulet')
    await user.click(await screen.findByRole('button', { name: /Poulet rôti/ }))
    await user.click(await screen.findByRole('button', { name: 'Ajouter Poulet rôti' }))

    await user.click(await screen.findByRole('button', { name: 'Retirer Poulet rôti' }))

    expect(screen.getByText(/Aucun ingrédient pour l’instant/)).toBeInTheDocument()
  })

  it('envoie la recette composée', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn()
    const spy = stubCreation(onCreate)
    renderRoute('/recettes/nouvelle')

    await user.type(await screen.findByLabelText('Nom'), 'Poulet riz')
    await user.type(screen.getByLabelText('Chercher un ingrédient'), 'poulet')
    await user.click(await screen.findByRole('button', { name: /Poulet rôti/ }))
    await user.click(await screen.findByRole('button', { name: 'Ajouter Poulet rôti' }))
    await user.click(screen.getByRole('button', { name: 'Créer la recette' }))

    await waitFor(() => expect(onCreate).toHaveBeenCalled())

    const request = spy.mock.calls.find(
      ([url, init]) => String(url).includes('/recipes/') && init?.method === 'POST',
    )
    const body = JSON.parse(String(request![1]?.body))
    expect(body).toMatchObject({ name: 'Poulet riz', servings: '2' })
    expect(body.ingredients).toEqual([{ food_id: 7, quantity: '100', unit_label: 'g' }])
  })
})
