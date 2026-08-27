import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated, recipeListItem } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function stubRecipes(respond: () => Response = () => jsonResponse(paginated([recipeListItem()]))) {
  return stubFetch([...BASE_ROUTES, { match: '/recipes/', respond }], () =>
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

describe('Liste des recettes', () => {
  it('affiche les recettes et leur valeur par portion', async () => {
    stubRecipes()
    renderRoute('/recettes')

    expect(await screen.findByRole('heading', { name: 'Recettes' })).toBeInTheDocument()
    const row = (await screen.findByRole('link', { name: /Poulet rôti/ })).closest(
      'li',
    ) as HTMLElement
    expect(within(row).getByText(/350/)).toBeInTheDocument()
    expect(within(row).getByText(/par portion/)).toBeInTheDocument()
  })

  it('invite à créer quand il n’y en a aucune', async () => {
    stubRecipes(() => jsonResponse(paginated([])))
    renderRoute('/recettes')

    expect(await screen.findByText('Aucune recette')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Créer une recette' })).toBeInTheDocument()
  })

  it('affiche un message lisible en cas d’échec', async () => {
    stubRecipes(() =>
      jsonResponse({ code: 'error', message: 'Service indisponible.', errors: {} }, 500),
    )
    renderRoute('/recettes')

    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible.')
  })

  it('met une recette en favori', async () => {
    const user = userEvent.setup()
    const favorite = vi.fn()
    stubFetch(
      [
        ...BASE_ROUTES,
        {
          match: '/favorite/',
          respond: () => {
            favorite()
            return new Response(null, { status: 204 })
          },
        },
        { match: '/recipes/', respond: () => jsonResponse(paginated([recipeListItem()])) },
      ],
      () => jsonResponse(paginated([])),
    )
    renderRoute('/recettes')

    await user.click(await screen.findByRole('button', { name: 'Ajouter Poulet rôti aux favoris' }))

    await waitFor(() => expect(favorite).toHaveBeenCalled())
  })
})
