import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ShoppingList, ShoppingListItem } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function item(overrides: Partial<ShoppingListItem> = {}): ShoppingListItem {
  return {
    id: 1,
    name: 'Poulet',
    food: 7,
    quantity: '450.000',
    unit_label: 'g',
    is_checked: false,
    sort_order: 0,
    source_type: 'recipe',
    ...overrides,
  }
}

function list(overrides: Partial<ShoppingList> = {}): ShoppingList {
  return {
    id: 4,
    name: 'Courses du samedi',
    visibility: 'private',
    items: [item()],
    is_editable: true,
    created_at: '2026-08-26T08:00:00Z',
    updated_at: '2026-08-26T08:00:00Z',
    ...overrides,
  }
}

function stubList(payload: ShoppingList = list(), calls: { patch?: () => void } = {}) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      {
        match: '/shopping-lists/4/items/',
        respond: () => {
          calls.patch?.()
          return jsonResponse(item(), 201)
        },
      },
      { match: '/shopping-lists/4/', respond: () => jsonResponse(payload) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function sent(spy: ReturnType<typeof stubFetch>, path: string, method: string) {
  return spy.mock.calls.find(([url, init]) => String(url).includes(path) && init?.method === method)
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Liste de courses', () => {
  it('affiche les articles et leur quantité regroupée', async () => {
    stubList()
    renderRoute('/courses/4')

    expect(await screen.findByRole('heading', { name: 'Courses du samedi' })).toBeInTheDocument()
    expect(screen.getByText('Poulet')).toBeInTheDocument()
    expect(screen.getByText('450 g')).toBeInTheDocument()
  })

  it('affiche « — » quand la quantité est inconnue', async () => {
    // « Du sel » est un article valable : inventer « 1 unité » serait une
    // donnée qu'on n'a pas (spec 01 §8).
    stubList(list({ items: [item({ name: 'Sel', food: null, quantity: null, unit_label: null })] }))
    renderRoute('/courses/4')

    expect(await screen.findByText('Sel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '—' })).toBeInTheDocument()
  })

  it('coche un article', async () => {
    const user = userEvent.setup()
    const spy = stubList()
    renderRoute('/courses/4')

    await user.click(await screen.findByLabelText('Marquer Poulet comme acheté'))

    await waitFor(() => expect(sent(spy, '/items/1/', 'PATCH')).toBeDefined())
  })

  it('barre un article acheté sans le déplacer', async () => {
    stubList(list({ items: [item({ is_checked: true })] }))
    renderRoute('/courses/4')

    expect(await screen.findByText('Poulet')).toHaveClass('line-through')
  })

  it('ajoute un article à la main', async () => {
    const user = userEvent.setup()
    const spy = stubList()
    renderRoute('/courses/4')

    await user.type(await screen.findByLabelText('Article'), 'Sel')
    const form = screen.getByLabelText('Article').closest('form') as HTMLElement
    await user.click(within(form).getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(sent(spy, '/shopping-lists/4/items/', 'POST')).toBeDefined())
    const body = JSON.parse(String(sent(spy, '/shopping-lists/4/items/', 'POST')![1]?.body))
    expect(body).toEqual({ name: 'Sel', quantity: null })
  })

  it('n’offre aucune écriture sur une liste reçue', async () => {
    // Le partage donne à lire (spec 05 §7).
    stubList(list({ is_editable: false }))
    renderRoute('/courses/4')

    await screen.findByText('Poulet')

    expect(screen.queryByLabelText(/Marquer .* comme acheté/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Article')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Supprimer la liste/ })).not.toBeInTheDocument()
    expect(screen.getByText(/consultation seule/)).toBeInTheDocument()
  })

  it('affiche un message lisible quand la liste est introuvable', async () => {
    stubFetch([...BASE_ROUTES], () =>
      jsonResponse({ code: 'not_found', message: 'Liste introuvable.', errors: {} }, 404),
    )
    renderRoute('/courses/4')

    expect(await screen.findByRole('alert')).toHaveTextContent('Liste introuvable.')
  })
})
