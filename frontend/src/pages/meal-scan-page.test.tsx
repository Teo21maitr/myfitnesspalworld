import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MealScanCandidate, MealScanSuggestion, MealScanTask } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { defaultMealTypeId } from '@/features/diary/meals'
import { renderRoute } from '@/test/render'

const TASK_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3301'

/** Les quatre repas par défaut, pour éprouver le choix. */
const MEALS = [
  {
    id: 1,
    name: 'Petit-déjeuner',
    slug: 'pdj',
    sort_order: 0,
    is_active: true,
    is_system: true,
    system_key: 'breakfast',
  },
  {
    id: 2,
    name: 'Déjeuner',
    slug: 'dej',
    sort_order: 1,
    is_active: true,
    is_system: true,
    system_key: 'lunch',
  },
  {
    id: 3,
    name: 'Dîner',
    slug: 'diner',
    sort_order: 2,
    is_active: true,
    is_system: true,
    system_key: 'dinner',
  },
  {
    id: 4,
    name: 'Collations',
    slug: 'coll',
    sort_order: 3,
    is_active: true,
    is_system: true,
    system_key: 'snacks',
  },
]

function candidate(overrides: Partial<MealScanCandidate> = {}): MealScanCandidate {
  return {
    id: 7,
    name: 'Poulet, cuisse, crue',
    brand: '',
    source: 'ciqual',
    source_label: 'Ciqual',
    reference_amount: '100.000',
    reference_unit: 'g',
    nutrition: {
      energy_kcal: '120.000',
      protein_g: '20.000',
      carbohydrates_g: null,
      fat_g: '4.000',
    },
    available_units: ['g', 'kg'],
    ...overrides,
  }
}

function suggestion(overrides: Partial<MealScanSuggestion> = {}): MealScanSuggestion {
  return {
    label: 'poulet',
    estimated_quantity: '150.000',
    unit: 'g',
    confidence: 0.82,
    alternatives: [],
    candidates: [candidate()],
    ...overrides,
  }
}

function task(overrides: Partial<MealScanTask> = {}): MealScanTask {
  return {
    id: TASK_ID,
    task_type: 'meal_scan',
    status: 'success',
    progress: 100,
    result: { suggestions: [suggestion()] },
    error: null,
    created_at: '2026-08-27T12:00:00Z',
    ...overrides,
  }
}

function stubStatus(enabled: boolean | (() => Response) = true) {
  return typeof enabled === 'function' ? enabled : () => jsonResponse({ enabled })
}

function stubScan(payload: MealScanTask | (() => Response) = task()) {
  const scan = typeof payload === 'function' ? payload : () => jsonResponse(payload, 202)
  const detail =
    typeof payload === 'function' ? () => jsonResponse(task(), 200) : () => jsonResponse(payload)

  return stubFetch(
    [
      // Devant `BASE_ROUTES`, qui n'expose qu'un seul repas : il en faut
      // plusieurs pour éprouver le choix.
      { match: '/meal-types/', respond: () => jsonResponse(MEALS) },
      ...BASE_ROUTES,
      { match: '/ai/status/', respond: () => jsonResponse({ enabled: true }) },
      { match: '/ai/meal-scan/', respond: scan },
      { match: `/tasks/${TASK_ID}/`, respond: detail },
      { match: '/diary/entries/', respond: () => jsonResponse({ id: 1 }, 201) },
    ],
    () => jsonResponse(paginated([])),
  )
}

function photo(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], 'repas.jpg', { type: 'image/jpeg' })
}

async function analyze(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(await screen.findByLabelText('Importer une photo du repas'), photo())
  await user.click(await screen.findByRole('button', { name: 'Analyser' }))
}

function sent(spy: ReturnType<typeof stubFetch>, path: string, method: string) {
  return spy.mock.calls.filter(
    ([url, init]) => String(url).includes(path) && init?.method === method,
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Meal Scan', () => {
  it('affiche les aliments détectés après l’analyse', async () => {
    const user = userEvent.setup()
    stubScan()
    renderRoute('/scanner-repas')

    await analyze(user)

    expect(await screen.findByText('poulet')).toBeInTheDocument()
    expect(screen.getByText('Confiance du modèle : 82 %')).toBeInTheDocument()
  })

  it('affiche les calories de la fiche, pas celles de la photo', async () => {
    const user = userEvent.setup()
    stubScan()
    renderRoute('/scanner-repas')

    await analyze(user)

    // 120 kcal aux 100 g, pour 150 g.
    expect(
      await screen.findByText(/Environ 180 kcal, d’après la fiche de l’aliment/),
    ).toBeInTheDocument()
  })

  it('ne journalise rien tant que l’utilisateur n’a pas confirmé', async () => {
    const user = userEvent.setup()
    const spy = stubScan()
    renderRoute('/scanner-repas')

    await analyze(user)
    await screen.findByText('poulet')

    expect(sent(spy, '/diary/entries/', 'POST')).toHaveLength(0)
  })

  it('crée une entrée par aliment retenu', async () => {
    const user = userEvent.setup()
    const spy = stubScan(
      task({
        result: {
          suggestions: [
            suggestion(),
            suggestion({
              label: 'abricot',
              estimated_quantity: '80.000',
              candidates: [candidate({ id: 9, name: 'Abricot, cru' })],
            }),
          ],
        },
      }),
    )
    renderRoute('/scanner-repas')

    await analyze(user)
    await user.click(await screen.findByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => expect(sent(spy, '/diary/entries/', 'POST')).toHaveLength(2))

    const body = JSON.parse(String(sent(spy, '/diary/entries/', 'POST')[0]?.[1]?.body))
    expect(body).toMatchObject({ food_id: 7, quantity: '150', unit_label: 'g' })
  })

  it('retire une ligne de la confirmation', async () => {
    const user = userEvent.setup()
    const spy = stubScan(
      task({
        result: {
          suggestions: [
            suggestion(),
            suggestion({ label: 'abricot', candidates: [candidate({ id: 9 })] }),
          ],
        },
      }),
    )
    renderRoute('/scanner-repas')

    await analyze(user)
    await user.click(await screen.findByRole('button', { name: 'Retirer abricot' }))
    await user.click(screen.getByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => expect(sent(spy, '/diary/entries/', 'POST')).toHaveLength(1))
  })

  it('propose la recherche manuelle quand rien ne correspond', async () => {
    const user = userEvent.setup()
    stubScan(task({ result: { suggestions: [suggestion({ label: 'zorglub', candidates: [] })] } }))
    renderRoute('/scanner-repas')

    await analyze(user)

    expect(await screen.findByText(/Aucun aliment de la base ne correspond/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Chercher cet aliment' })).toHaveAttribute(
      'href',
      '/aliments?q=zorglub',
    )
  })

  it('annonce une photo sans aliment reconnu', async () => {
    const user = userEvent.setup()
    stubScan(task({ result: { suggestions: [] } }))
    renderRoute('/scanner-repas')

    await analyze(user)

    expect(await screen.findByText(/Aucun aliment n’a été reconnu/)).toBeInTheDocument()
  })

  it('affiche l’échec de l’analyse et propose de recommencer', async () => {
    const user = userEvent.setup()
    stubScan(
      task({
        status: 'failed',
        result: null,
        error: 'Le fournisseur d’IA est injoignable.',
      }),
    )
    renderRoute('/scanner-repas')

    await analyze(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('injoignable')
    expect(screen.getByRole('button', { name: 'Reprendre une photo' })).toBeInTheDocument()
  })

  it('explique que l’IA est coupée sans bloquer le reste', async () => {
    const user = userEvent.setup()
    stubScan(() =>
      jsonResponse(
        { code: 'ai_disabled', message: 'L’analyse par IA est momentanément indisponible.' },
        503,
      ),
    )
    renderRoute('/scanner-repas')

    await analyze(user)

    expect(await screen.findByText(/L’analyse par IA est indisponible/)).toBeInTheDocument()
  })
})

describe('disponibilité de l’IA', () => {
  it('annonce l’indisponibilité dès l’ouverture, sans faire cadrer de photo', async () => {
    // Le défaut qu'on corrige : l'écran ne le disait qu'après l'envoi.
    stubFetch([...BASE_ROUTES, { match: '/ai/status/', respond: stubStatus(false) }], () =>
      jsonResponse(paginated([])),
    )
    renderRoute('/scanner-repas')

    expect(await screen.findByText(/L’analyse par IA est indisponible/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ouvrir la caméra' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Chercher un aliment' })).toBeInTheDocument()
  })

  it('laisse l’écran utilisable quand la disponibilité est inconnue', async () => {
    // Une panne de cette requête ne doit pas condamner la fonctionnalité.
    stubFetch(
      [
        ...BASE_ROUTES,
        {
          match: '/ai/status/',
          respond: () => jsonResponse({ code: 'error', message: 'nope' }, 500),
        },
      ],
      () => jsonResponse(paginated([])),
    )
    renderRoute('/scanner-repas')

    expect(await screen.findByRole('button', { name: 'Ouvrir la caméra' })).toBeInTheDocument()
  })
})

describe('choix du repas', () => {
  it('propose le repas qui correspond à l’heure', async () => {
    // Le premier de la liste revenait à proposer « Petit-déjeuner » à toute
    // heure : un dîner scanné à 20 h y atterrissait sans qu'on le voie.
    //
    // L'heure n'est pas figée ici — des minuteurs simulés bloqueraient les
    // attentes de Testing Library. La correspondance heure → repas est couverte
    // exhaustivement par `meals.test.ts` ; ce test vérifie que l'écran s'en
    // sert, à n'importe quelle heure.
    const user = userEvent.setup()
    stubScan()
    renderRoute('/scanner-repas')

    await analyze(user)

    expect(await screen.findByLabelText('Ajouter à')).toHaveValue(defaultMealTypeId(MEALS))
  })

  it('journalise dans le repas retenu', async () => {
    const user = userEvent.setup()
    const spy = stubScan()
    renderRoute('/scanner-repas')

    await analyze(user)
    await user.selectOptions(await screen.findByLabelText('Ajouter à'), '2')
    await user.click(screen.getByRole('button', { name: 'Ajouter au journal' }))

    await waitFor(() => expect(sent(spy, '/diary/entries/', 'POST')).toHaveLength(1))
    const body = JSON.parse(String(sent(spy, '/diary/entries/', 'POST')[0]?.[1]?.body))
    expect(body.meal_type_id).toBe(2)
  })

  it('le choix précède la liste des aliments', async () => {
    // Il décide où tout atterrit : il n'a rien à faire sous une pile de cartes.
    const user = userEvent.setup()
    stubScan()
    renderRoute('/scanner-repas')

    await analyze(user)

    const choix = await screen.findByLabelText('Ajouter à')
    const premierAliment = screen.getByText('poulet')
    expect(choix.compareDocumentPosition(premierAliment)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })
})
