import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Dashboard, NutritionValues } from '@/lib/api/types'
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

const MEAL = {
  id: 1,
  name: 'Petit-déjeuner',
  slug: 'petit-dejeuner',
  sort_order: 0,
  is_active: true,
  is_system: true,
  system_key: 'breakfast',
}

const NUTRIENTS = [
  'energy_kcal',
  'protein_g',
  'carbohydrates_g',
  'fat_g',
  'fiber_g',
  'sugars_g',
  'sodium_mg',
  'salt_g',
  'cholesterol_mg',
  'potassium_mg',
  'calcium_mg',
  'iron_mg',
  'magnesium_mg',
  'vitamin_a_ug',
  'vitamin_b6_mg',
  'vitamin_b12_ug',
  'vitamin_c_mg',
  'vitamin_d_ug',
  'vitamin_e_mg',
  'vitamin_k_ug',
] as const

function nutrition(values: Partial<NutritionValues> = {}): NutritionValues {
  return Object.fromEntries(
    NUTRIENTS.map((key) => [key, values[key] ?? null]),
  ) as unknown as NutritionValues
}

function dashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    date: '2026-08-26',
    notes: '',
    goals: {
      date: '2026-08-26',
      weekday: 2,
      daily_calories: '2000.00',
      protein_g: '150.00',
      carbs_g: '200.00',
      fat_g: '67.00',
      fiber_g: null,
    },
    totals: nutrition({ energy_kcal: '450.000', protein_g: '25.000' }),
    incomplete_nutrients: [],
    remaining: {
      daily_calories: '1550.00',
      protein_g: '125.00',
      carbs_g: '200.00',
      fat_g: '67.00',
      fiber_g: null,
    },
    meals: [
      {
        meal_type: MEAL,
        entries: [],
        totals: nutrition({ energy_kcal: '450.000' }),
        incomplete_nutrients: [],
      },
    ],
    weight: {
      latest_kg: '77.60',
      latest_date: '2026-08-26',
      start_kg: '80.00',
      change_kg: '-2.40',
      target_kg: '70.00',
      progress_percent: '24.0',
    },
    ...overrides,
  }
}

/** Carte portant ce titre. Le total du repas affiche la même valeur ailleurs. */
function card(title: string): HTMLElement {
  const heading = screen.getByRole('heading', { name: title })
  return heading.closest('[data-slot="card"]') as HTMLElement
}

function stubDashboard(payload: () => Response = () => jsonResponse(dashboard())) {
  return stubFetch(
    [
      { match: '/auth/me/', respond: () => jsonResponse(USER) },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      { match: '/dashboard/', respond: payload },
    ],
    () => jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Accueil', () => {
  it('affiche les calories consommées et restantes', async () => {
    stubDashboard()
    renderRoute('/')

    expect(await screen.findByRole('heading', { name: 'Aujourd’hui' })).toBeInTheDocument()
    await screen.findByRole('heading', { name: 'Calories' })

    const calories = card('Calories')
    expect(within(calories).getByText('450')).toBeInTheDocument()
    expect(within(calories).getByText(/restantes/)).toBeInTheDocument()
    expect(within(calories).getByText('1 550')).toBeInTheDocument()
  })

  it('affiche les macronutriments et les repas', async () => {
    stubDashboard()
    renderRoute('/')

    expect(await screen.findByText('Protéines')).toBeInTheDocument()
    expect(screen.getByText('Repas du jour')).toBeInTheDocument()
    expect(screen.getByText('Petit-déjeuner')).toBeInTheDocument()
  })

  it('affiche le poids et le chemin parcouru', async () => {
    stubDashboard()
    renderRoute('/')

    expect(await screen.findByText('77,6')).toBeInTheDocument()
    expect(screen.getByText(/2,4 kg depuis le début/)).toBeInTheDocument()
    expect(screen.getByText(/24 % du chemin vers/)).toBeInTheDocument()
  })

  it('invite à définir un objectif quand il n’y en a pas', async () => {
    stubDashboard(() => jsonResponse(dashboard({ goals: null, remaining: null })))
    renderRoute('/')

    expect(await screen.findByText(/Aucun objectif défini/)).toBeInTheDocument()
  })

  it('invite à se peser quand aucune pesée n’existe', async () => {
    stubDashboard(() =>
      jsonResponse(
        dashboard({
          weight: {
            latest_kg: null,
            latest_date: null,
            start_kg: null,
            change_kg: null,
            target_kg: null,
            progress_percent: null,
          },
        }),
      ),
    )
    renderRoute('/')

    expect(await screen.findByText(/Aucune pesée enregistrée/)).toBeInTheDocument()
  })

  it('affiche un message lisible quand le tableau de bord échoue', async () => {
    stubDashboard(() =>
      jsonResponse({ code: 'error', message: 'Service indisponible.', errors: {} }, 500),
    )
    renderRoute('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible.')
  })

  it('propose les raccourcis d’ajout', async () => {
    stubDashboard()
    renderRoute('/')

    await screen.findByRole('heading', { name: 'Ajouter' })

    // La navigation propose aussi certains de ces liens : on cible la carte.
    const shortcuts = within(card('Ajouter'))
    expect(shortcuts.getByRole('link', { name: 'Ajouter un aliment' })).toBeInTheDocument()
    expect(shortcuts.getByRole('link', { name: 'Scanner' })).toBeInTheDocument()
    expect(shortcuts.getByRole('link', { name: 'Ajout rapide' })).toBeInTheDocument()
  })
})
