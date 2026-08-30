import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProgressPhotoGroup } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function group(overrides: Partial<ProgressPhotoGroup> = {}): ProgressPhotoGroup {
  return {
    id: 3,
    date: '2026-08-26',
    weight_kg_snapshot: '78.40',
    notes: 'Fin de cycle',
    photos: [
      {
        id: 11,
        photo_type: 'front',
        photo_type_label: 'Face',
        url: 'https://seau.test/abc?expires=300',
        size_bytes: 40_000,
        created_at: '2026-08-26T08:00:00Z',
      },
      {
        id: 12,
        photo_type: 'side',
        photo_type_label: 'Profil',
        url: 'https://seau.test/def?expires=300',
        size_bytes: 41_000,
        created_at: '2026-08-26T08:00:00Z',
      },
    ],
    created_at: '2026-08-26T08:00:00Z',
    updated_at: '2026-08-26T08:00:00Z',
    ...overrides,
  }
}

function stubPhotos(respond?: () => Response) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      {
        match: '/progress/photos/',
        respond: respond ?? (() => jsonResponse(paginated([group()]))),
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

describe('photos de progression', () => {
  it('dit que les photos ne sont jamais partageables', async () => {
    // L'utilisateur n'a pas à deviner ce que l'application fait de ses images.
    stubPhotos()
    renderRoute('/photos')

    expect(await screen.findByText(/jamais partageables/)).toBeInTheDocument()
  })

  it('affiche les photos d’une date avec leur angle', async () => {
    stubPhotos()
    renderRoute('/photos')

    const liste = await screen.findByRole('list', { name: 'Photos de progression' })
    expect(within(liste).getByAltText('Face — 2026-08-26')).toBeInTheDocument()
    expect(within(liste).getByAltText('Profil — 2026-08-26')).toBeInTheDocument()
    expect(liste).toHaveTextContent('78.4 kg')
    expect(liste).toHaveTextContent('Fin de cycle')
  })

  it('demande confirmation avant de supprimer', async () => {
    // La suppression est définitive : le fichier part avec la ligne.
    const user = userEvent.setup()
    const spy = stubPhotos()
    renderRoute('/photos')
    await screen.findByRole('list', { name: 'Photos de progression' })

    await user.click(screen.getByRole('button', { name: /Supprimer les photos du/ }))

    expect(screen.getByText('Définitif ?')).toBeInTheDocument()
    expect(spy.mock.calls.find(([, init]) => init?.method === 'DELETE')).toBeUndefined()
  })

  it('supprime une seule photo une fois confirmé', async () => {
    const user = userEvent.setup()
    const spy = stubPhotos()
    renderRoute('/photos')
    await screen.findByRole('list', { name: 'Photos de progression' })

    await user.click(screen.getByRole('button', { name: 'Supprimer Face' }))
    await user.click(screen.getByRole('button', { name: /^Supprimer$/ }))

    const appel = spy.mock.calls.find(
      ([url, init]) => String(url).includes('/photos/3/files/11/') && init?.method === 'DELETE',
    )
    expect(appel).toBeDefined()
  })

  it('propose un état vide explicite', async () => {
    stubPhotos(() => jsonResponse(paginated([])))
    renderRoute('/photos')

    expect(await screen.findByText(/Aucune photo pour l’instant/)).toBeInTheDocument()
  })

  it('signale une erreur sans casser l’écran', async () => {
    stubPhotos(() =>
      jsonResponse({ code: 'server_error', message: 'Erreur serveur.', errors: {} }, 500),
    )
    renderRoute('/photos')

    expect(await screen.findByRole('alert')).toHaveTextContent(/Erreur serveur/)
  })

  it('n’expose jamais la clé de stockage', async () => {
    // Elle est non devinable, donc secrète : le serveur ne la rend pas, et
    // rien à l'écran ne doit la reconstituer.
    stubPhotos()
    renderRoute('/photos')
    await screen.findByRole('list', { name: 'Photos de progression' })

    expect(document.body.innerHTML).not.toContain('storage_key')
  })
})
