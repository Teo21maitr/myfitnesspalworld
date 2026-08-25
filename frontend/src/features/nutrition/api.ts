import { api } from '@/lib/api/client'
import type {
  ActivityLevel,
  CalorieEstimate,
  CurrentGoal,
  DayOverride,
  GoalType,
  NutritionGoal,
  Paginated,
  SexForCalculation,
  ValueSource,
  WeightEntry,
} from '@/lib/api/types'

export const goalsQueryKey = ['nutrition', 'goals'] as const
export const currentGoalQueryKey = ['nutrition', 'goals', 'current'] as const
export const weightQueryKey = ['progress', 'weight'] as const

/** Entrées du calcul calorique, telles qu'attendues par le backend. */
export interface CalculationPayload {
  birth_date: string
  sex_for_calculation: SexForCalculation
  height_cm: string
  weight_kg: string
  activity_level: ActivityLevel
  goal_type: GoalType
  goal_rate_kg_per_week?: string | null
  target_weight_kg?: string | null
}

export interface OnboardingPayload extends CalculationPayload {
  daily_calories: string
  protein_g: string
  carbs_g: string
  fat_g: string
  fiber_g?: string | null
  calories_source: ValueSource
  macros_source: ValueSource
}

export interface OnboardingResult {
  goal: NutritionGoal
  warnings: string[]
  notice: string
}

export interface GoalPayload {
  daily_calories: string
  protein_g: string
  carbs_g: string
  fat_g: string
  fiber_g?: string | null
  calories_source?: ValueSource
  macros_source?: ValueSource
}

/** Le calcul vit côté serveur : le frontend n'estime jamais de calories. */
export const calculateCalories = (payload: CalculationPayload) =>
  api.post<CalorieEstimate>('/profile/goals/calculate/', payload)

export const submitOnboarding = (payload: OnboardingPayload) =>
  api.post<OnboardingResult>('/profile/onboarding/', payload)

export const fetchGoals = () => api.get<Paginated<NutritionGoal>>('/profile/goals/')

export const fetchCurrentGoal = () => api.get<CurrentGoal>('/profile/goals/current/')

export const createGoal = (payload: GoalPayload) =>
  api.post<NutritionGoal>('/profile/goals/', payload)

export const updateGoal = (id: number, payload: Partial<GoalPayload>) =>
  api.patch<NutritionGoal>(`/profile/goals/${id}/`, payload)

export const setDayOverride = (
  goalId: number,
  weekday: number,
  payload: Partial<Omit<DayOverride, 'id' | 'weekday' | 'weekday_label'>>,
) => api.put<DayOverride>(`/profile/goals/${goalId}/overrides/${weekday}/`, payload)

export const deleteDayOverride = (goalId: number, weekday: number) =>
  api.delete<void>(`/profile/goals/${goalId}/overrides/${weekday}/`)

export const fetchWeightEntries = () => api.get<Paginated<WeightEntry>>('/progress/weight/')

export const saveWeight = (payload: { date: string; weight_kg: string; notes?: string | null }) =>
  api.post<WeightEntry>('/progress/weight/', payload)
