import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { LabelScanResult, LabelScanTask } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

const TASK_ID = '9f2504e0-4f89-11d3-9a0c-0305e82c3301'

function result(overrides: Partial<LabelScanResult> = {}): LabelScanResult {
  return {
    basis: '100g',
    draft: {
      name: 'Knäckebröd',
      brand: 'Wasa',
      barcode: '7300400481106',
      reference_amount: '100',
      reference_unit: 'g',
      nutrition: {
        energy_kcal: '336.000',
        protein_g: '10.000',
        carbohydrates_g: '58.000',
        sugars_g: '1.500',
        fat_g: '1.700',
        fiber_g: null,
        salt_g: '1.100',
        sodium_mg: null,
      },
    },
    unreadable: ['fiber_g', 'sodium_mg'],
    ...overrides,
  }
}

function task(overrides: Partial<LabelScanTask> = {}): LabelScanTask {
  return {
    id: TASK_ID,
    task_type: 'label_scan',
    status: 'success',
    progress: 100,
    result: result(),
    error: null,
    created_at: '2026-08-28T12:00:00Z',
    ...overrides,
  }
}

function stubScan(payload: LabelScanTask = task(), enabled = true) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      { match: '/ai/status/', respond: () => jsonResponse({ enabled }) },
      { match: '/ai/label-scan/', respond: () => jsonResponse(payload, 202) },
      { match: `/tasks/${TASK_ID}/`, respond: () => jsonResponse(payload) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function photo(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], 'etiquette.jpg', {
    type: 'image/jpeg',
  })
}

async function analyze(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(await screen.findByLabelText('Importer une photo de l’étiquette'), photo())
  await user.click(await screen.findByRole('button', { name: 'Lire l’étiquette' }))
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('lecture d’étiquette', () => {
  it('préremplit le formulaire avec ce que la photo a donné', async () => {
    const user = userEvent.setup()
    stubScan()
    renderRoute('/scanner-etiquette')

    await analyze(user)

    expect(await screen.findByLabelText('Nom')).toHaveValue('Knäckebröd')
    expect(screen.getByLabelText('Marque (facultatif)')).toHaveValue('Wasa')
    expect(screen.getByLabelText(/Énergie/)).toHaveValue(336)
    expect(screen.getByLabelText(/dont sucres/)).toHaveValue(1.5)
    expect(screen.getByLabelText(/^Sel/)).toHaveValue(1.1)
  })

  it('laisse vide ce que la photo n’a pas donné, et le dit', async () => {
    // Un champ vide pourrait passer pour un oubli de saisie : l'écran nomme ce
    // qui manque plutôt que de laisser croire à un zéro (spec 01 §8).
    const user = userEvent.setup()
    stubScan()
    renderRoute('/scanner-etiquette')

    await analyze(user)

    expect(await screen.findByLabelText(/Fibres/)).toHaveValue(null)
    expect(screen.getByText(/La photo n’a pas donné : fibres et sodium/)).toBeInTheDocument()
  })

  it('refuse de reprendre des valeurs sans colonne pour 100', async () => {
    // Une colonne « par portion » recopiée telle quelle fausserait tout.
    const user = userEvent.setup()
    const vide = result({
      basis: 'unknown',
      draft: {
        ...result().draft,
        nutrition: Object.fromEntries(
          Object.keys(result().draft.nutrition).map((name) => [name, null]),
        ) as LabelScanResult['draft']['nutrition'],
      },
    })
    stubScan(task({ result: vide }))
    renderRoute('/scanner-etiquette')

    await analyze(user)

    expect(await screen.findByText(/Aucune colonne « pour 100 g »/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Énergie/)).toHaveValue(null)
  })

  it('annonce l’indisponibilité de l’IA dès l’ouverture', async () => {
    stubScan(task(), false)
    renderRoute('/scanner-etiquette')

    expect(await screen.findByText(/L’analyse par IA est indisponible/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ouvrir la caméra' })).not.toBeInTheDocument()
  })

  it('affiche l’échec et propose de recommencer', async () => {
    const user = userEvent.setup()
    stubScan(
      task({ status: 'failed', result: null, error: 'Le fournisseur d’IA est injoignable.' }),
    )
    renderRoute('/scanner-etiquette')

    await analyze(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('injoignable')
    expect(screen.getByRole('button', { name: 'Reprendre une photo' })).toBeInTheDocument()
  })
})
