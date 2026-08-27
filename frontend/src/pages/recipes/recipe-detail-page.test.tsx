import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { RecipeDetail } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated, recipeDetail, recipeNutrition } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function stubRecipe(
  recipe: RecipeDetail = recipeDetail(),
  extra: { addToDiary?: (body: string) => void } = {},
) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      {
        match: '/add-to-diary/',
        respond: () => {
          extra.addToDiary?.('')
          return jsonResponse({ id: 1 }, 201)
        },
      },
      { match: '/recipes/3/', respond: () => jsonResponse(recipe) },
    ],
    () => jsonResponse(paginated([])),
  )
}

/** Carte portant ce titre : plusieurs blocs affichent des valeurs voisines. */
function card(title: string): HTMLElement {
  return screen.getByRole('heading', { name: title }).closest('[data-slot="card"]') as HTMLElement
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Fiche recette', () => {
  it('affiche les valeurs pour une portion', async () => {
    stubRecipe()
    renderRoute('/recettes/3')

    expect(await screen.findByRole('heading', { name: 'Poulet rôti' })).toBeInTheDocument()
    const portion = within(card('Pour une portion'))
    // La valeur paraît deux fois : en résumé et dans le tableau détaillé.
    expect(portion.getByText(/par portion/)).toHaveTextContent('350')
    expect(portion.getByText('Macronutriments')).toBeInTheDocument()
  })

  it('nomme les nutriments dont le total est partiel', async () => {
    stubRecipe(
      recipeDetail({
        nutrition: recipeNutrition({ energy_kcal: '350.000', fiber_g: '2.000' }, ['fiber_g']),
      }),
    )
    renderRoute('/recettes/3')

    // Nommer le nutriment, et non annoncer un décompte anonyme.
    expect(await screen.findByText(/Total partiel : Fibres/)).toBeInTheDocument()
    expect(screen.getByText(/sans compter les inconnues pour zéro/)).toBeInTheDocument()
  })

  it('marque la valeur mise en avant quand l’énergie est partielle', async () => {
    // Le chiffre annoncé est alors sous-évalué : le taire le ferait passer
    // pour un total exact.
    stubRecipe(
      recipeDetail({
        nutrition: recipeNutrition({ energy_kcal: '45.900' }, ['energy_kcal']),
      }),
    )
    renderRoute('/recettes/3')

    expect(await screen.findByText(/par portion — total partiel/)).toBeInTheDocument()
  })

  it('n’affiche aucun avertissement quand tout est renseigné', async () => {
    stubRecipe()
    renderRoute('/recettes/3')

    await screen.findByRole('heading', { name: 'Pour une portion' })

    expect(screen.queryByText(/Total partiel/)).not.toBeInTheDocument()
  })

  it('signale un ingrédient dont l’aliment a disparu', async () => {
    stubRecipe(
      recipeDetail({
        ingredients: [
          {
            id: 1,
            food: null,
            food_name: 'Poulet',
            quantity: '200.000',
            unit_label: 'g',
            sort_order: 0,
          },
        ],
      }),
    )
    renderRoute('/recettes/3')

    expect(await screen.findByText('aliment supprimé')).toBeInTheDocument()
  })

  it('ajoute des portions au journal', async () => {
    const user = userEvent.setup()
    const addToDiary = vi.fn()
    stubRecipe(recipeDetail(), { addToDiary })
    renderRoute('/recettes/3')

    const form = (await screen.findByLabelText('Portions')).closest('form') as HTMLElement
    await user.click(within(form).getByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => expect(addToDiary).toHaveBeenCalled())
  })

  it('propose de modifier et de supprimer sa propre recette', async () => {
    stubRecipe()
    renderRoute('/recettes/3')

    expect(await screen.findByRole('link', { name: 'Modifier' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Supprimer' })).toBeInTheDocument()
  })

  it('n’offre ni modification ni suppression sur une recette reçue', async () => {
    stubRecipe(recipeDetail({ is_editable: false }))
    renderRoute('/recettes/3')

    await screen.findByRole('heading', { name: 'Poulet rôti' })

    expect(screen.queryByRole('link', { name: 'Modifier' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Supprimer' })).not.toBeInTheDocument()
    // Copier chez soi reste possible (spec 01 §18).
    expect(screen.getByRole('button', { name: 'Dupliquer' })).toBeInTheDocument()
  })

  it('affiche un message lisible quand la recette est introuvable', async () => {
    stubFetch([...BASE_ROUTES], () =>
      jsonResponse({ code: 'not_found', message: 'Recette introuvable.', errors: {} }, 404),
    )
    renderRoute('/recettes/3')

    expect(await screen.findByRole('alert')).toHaveTextContent('Recette introuvable.')
  })
})
