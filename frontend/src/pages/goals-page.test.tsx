import { screen, waitFor, within } from '@testing-library/react'
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

const GOAL = {
  id: 7,
  daily_calories: '2209.00',
  protein_g: '166.00',
  carbs_g: '221.00',
  fat_g: '74.00',
  fiber_g: null,
  net_carbs_g: null,
  macro_mode: 'percentage',
  calories_source: 'calculated',
  macros_source: 'calculated',
  start_date: '2026-08-01',
  end_date: null,
  is_current: true,
  macro_calories_gap: '0.00',
  day_overrides: [],
  created_at: '2026-08-01T10:00:00+02:00',
}

const PAST_GOAL = {
  ...GOAL,
  id: 3,
  daily_calories: '2400.00',
  start_date: '2026-01-01',
  end_date: '2026-07-31',
  is_current: false,
}

const TODAY = {
  date: '2026-08-24',
  weekday: 0,
  daily_calories: '2209.00',
  protein_g: '166.00',
  carbs_g: '221.00',
  fat_g: '74.00',
  fiber_g: null,
}

interface StubOptions {
  goal?: typeof GOAL | null
  history?: unknown[]
  onPatch?: (body: unknown) => void
  onOverride?: (body: unknown) => void
}

function stubGoals({
  goal = GOAL,
  history = [GOAL, PAST_GOAL],
  onPatch,
  onOverride,
}: StubOptions = {}) {
  return stubFetch([
    { match: '/auth/me/', respond: () => jsonResponse(USER) },
    {
      match: '/profile/settings/',
      respond: () =>
        jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
    },
    {
      match: '/profile/goals/current/',
      respond: () =>
        goal
          ? jsonResponse({ goal, today: TODAY })
          : jsonResponse({ code: 'not_found', message: 'Aucun objectif.', errors: {} }, 404),
    },
    {
      match: '/overrides/',
      respond: () => {
        onOverride?.(null)
        return jsonResponse({
          id: 1,
          weekday: 5,
          weekday_label: 'samedi',
          daily_calories: '2500.00',
          protein_g: null,
          carbs_g: null,
          fat_g: null,
          fiber_g: null,
          enabled: true,
        })
      },
    },
    {
      match: '/profile/goals/7/',
      respond: () => {
        onPatch?.(null)
        return jsonResponse({ ...GOAL, daily_calories: '1900.00' })
      },
    },
    {
      match: '/profile/goals/',
      respond: () =>
        jsonResponse({ count: history.length, next: null, previous: null, results: history }),
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

describe('Page Objectifs', () => {
  it('affiche les valeurs du jour', async () => {
    stubGoals()
    renderRoute('/objectifs')

    expect(await screen.findByRole('heading', { name: 'Objectifs' })).toBeInTheDocument()

    const today = within(await screen.findByTestId('goal-summary'))
    expect(today.getByText('2209')).toBeInTheDocument()
    expect(today.getByText('166')).toBeInTheDocument()
  })

  it('affiche l’historique des objectifs passés', async () => {
    stubGoals()
    renderRoute('/objectifs')

    expect(await screen.findByRole('heading', { name: 'Historique' })).toBeInTheDocument()
    expect(screen.getByText('2400 kcal')).toBeInTheDocument()
  })

  it('signale l’absence d’objectif', async () => {
    stubGoals({ goal: null, history: [] })
    renderRoute('/objectifs')

    expect(await screen.findByRole('heading', { name: 'Aucun objectif' })).toBeInTheDocument()
  })

  it('permet de modifier l’objectif courant', async () => {
    const user = userEvent.setup()
    const onPatch = vi.fn()
    stubGoals({ onPatch })
    renderRoute('/objectifs')

    const field = await screen.findByLabelText('Calories')
    await user.clear(field)
    await user.type(field, '1900')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(onPatch).toHaveBeenCalled()
    })
  })

  it('permet de poser une surcharge de jour', async () => {
    const user = userEvent.setup()
    const onOverride = vi.fn()
    stubGoals({ onOverride })
    renderRoute('/objectifs')

    await user.click(await screen.findByRole('button', { name: 'Samedi' }))
    await user.type(screen.getByLabelText('Calories du samedi'), '2500')
    await user.click(screen.getByRole('button', { name: 'Enregistrer la surcharge' }))

    await waitFor(() => {
      expect(onOverride).toHaveBeenCalled()
    })
  })
})
