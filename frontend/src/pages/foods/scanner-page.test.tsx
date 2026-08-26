import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { renderRoute } from '@/test/render'

const USER = {
  id: 1,
  username: 'teo',
  first_name: 'Téo',
  last_name: 'Maitrot',
  email: null,
  status: 'ACTIVE',
  is_staff: false,
  onboarding_completed: true,
}

const BARCODE = '3017620422003'

const FOOD = {
  id: 7,
  name: 'Nutella',
  brand: 'Nutella',
  source: 'off',
  source_label: 'Open Food Facts',
  reference_amount: '100.00',
  reference_unit: 'g',
  energy_kcal: '539.000',
  is_favorite: false,
  is_own: false,
  is_verified: false,
  barcode: BARCODE,
  visibility: 'private',
  default_unit_type: 'g',
  nutrition: null,
  portions: [],
  available_units: ['g', 'kg'],
  is_editable: false,
  created_at: '2026-08-25T10:00:00Z',
  updated_at: '2026-08-25T10:00:00Z',
}

interface StubOptions {
  /** Réponse de `/barcodes/{code}/`. */
  barcode?: () => Response
  onLookup?: (url: string) => void
}

function stubScanner({ barcode, onLookup }: StubOptions = {}) {
  return stubFetch([
    { match: '/auth/me/', respond: () => jsonResponse(USER) },
    {
      match: '/profile/settings/',
      respond: () =>
        jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
    },
    // Route spécifique avant la générique : la fiche est consultée après
    // la redirection.
    { match: `/foods/${FOOD.id}/`, respond: () => jsonResponse(FOOD) },
    { match: '/foods/', respond: () => jsonResponse({ count: 0, results: [] }) },
    {
      match: '/barcodes/',
      respond: () => {
        onLookup?.('')
        return barcode ? barcode() : jsonResponse(FOOD)
      },
    },
  ])
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Scanner', () => {
  it('offre la saisie manuelle sans exiger la caméra', async () => {
    stubScanner()
    renderRoute('/scanner')

    // La saisie manuelle ne doit jamais être reléguée derrière un échec de
    // caméra : un geste n'est jamais l'unique moyen d'agir (spec 06 §6).
    expect(await screen.findByLabelText('Code-barres')).toBeInTheDocument()
  })

  it('n’interroge pas le serveur sur un code trop court', async () => {
    const user = userEvent.setup()
    const onLookup = vi.fn()
    stubScanner({ onLookup })
    renderRoute('/scanner')

    await user.type(await screen.findByLabelText('Code-barres'), '123')

    expect(await screen.findByText(/entre 8 et 24 chiffres/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Chercher ce produit/ })).toBeDisabled()
    expect(onLookup).not.toHaveBeenCalled()
  })

  it('ouvre la fiche du produit trouvé', async () => {
    const user = userEvent.setup()
    stubScanner()
    const { router } = renderRoute('/scanner')

    await user.type(await screen.findByLabelText('Code-barres'), BARCODE)
    await user.click(screen.getByRole('button', { name: /Chercher ce produit/ }))

    expect(await screen.findByText('Nutella')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/aliments/7')
  })

  it('propose la création avec le code prérempli quand le produit est inconnu', async () => {
    const user = userEvent.setup()
    stubScanner({
      barcode: () =>
        jsonResponse(
          {
            code: 'product_not_found',
            message: 'Ce produit est introuvable. Vous pouvez le créer vous-même.',
            errors: {},
          },
          404,
        ),
    })
    renderRoute('/scanner')

    await user.type(await screen.findByLabelText('Code-barres'), BARCODE)
    await user.click(screen.getByRole('button', { name: /Chercher ce produit/ }))

    const creation = await screen.findByRole('link', { name: 'Créer ce produit' })
    expect(creation).toHaveAttribute('href', `/mes-aliments?creer=1&barcode=${BARCODE}`)
  })

  it('distingue une panne de la source d’un produit inconnu', async () => {
    const user = userEvent.setup()
    stubScanner({
      barcode: () =>
        jsonResponse(
          {
            code: 'external_source_unavailable',
            message: 'Open Food Facts est momentanément indisponible.',
            errors: {},
          },
          503,
        ),
    })
    renderRoute('/scanner')

    await user.type(await screen.findByLabelText('Code-barres'), BARCODE)
    await user.click(screen.getByRole('button', { name: /Chercher ce produit/ }))

    expect(await screen.findByText(/momentanément indisponible/)).toBeInTheDocument()
    // Une panne ne doit pas pousser à créer un doublon d'un produit existant.
    expect(screen.queryByRole('link', { name: 'Créer ce produit' })).not.toBeInTheDocument()
  })
})
