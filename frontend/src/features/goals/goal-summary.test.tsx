import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CurrentGoal } from '@/lib/api/types'

import { GoalSummary } from './goal-summary'

const GOAL: CurrentGoal['goal'] = {
  id: 1,
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

const TODAY: CurrentGoal['today'] = {
  date: '2026-08-25',
  weekday: 1,
  daily_calories: '2209.00',
  protein_g: '166.00',
  carbs_g: '221.00',
  fat_g: '74.00',
  fiber_g: null,
}

describe('GoalSummary', () => {
  it('affiche les valeurs du jour', () => {
    render(<GoalSummary current={{ goal: GOAL, today: TODAY }} />)

    expect(screen.getByText('2209')).toBeInTheDocument()
    expect(screen.getByText('166')).toBeInTheDocument()
  })

  it('ne signale aucune surcharge quand les valeurs sont identiques', () => {
    render(<GoalSummary current={{ goal: GOAL, today: TODAY }} />)

    expect(screen.queryByText(/surcharge est active/)).not.toBeInTheDocument()
  })

  it('ne se laisse pas tromper par une différence de formatage', () => {
    render(<GoalSummary current={{ goal: GOAL, today: { ...TODAY, daily_calories: '2209' } }} />)

    expect(screen.queryByText(/surcharge est active/)).not.toBeInTheDocument()
  })

  it('signale une surcharge réellement différente', () => {
    render(<GoalSummary current={{ goal: GOAL, today: { ...TODAY, daily_calories: '2400.00' } }} />)

    expect(screen.getByText(/surcharge est active/)).toBeInTheDocument()
  })
})
