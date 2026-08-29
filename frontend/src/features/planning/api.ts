import { api } from '@/lib/api/client'
import type {
  MealPlan,
  MealPlanListItem,
  MealPlanTask,
  Paginated,
  PlanProposal,
  ProposalDay,
} from '@/lib/api/types'

export const plansQueryKey = ['meal-plans'] as const
export const planQueryKey = (id: number) => ['meal-plans', 'detail', id] as const

export interface GenerateConstraints {
  name?: string
  start_date: string
  end_date: string
  meal_type_ids: number[]
  allergies?: string[]
  liked?: string[]
  disliked?: string[]
}

export const fetchPlans = () => api.get<Paginated<MealPlanListItem>>('/meal-plans/')

export const fetchPlan = (id: number) => api.get<MealPlan>(`/meal-plans/${id}/`)

/**
 * Lance la composition d'une proposition (spec 04 §8).
 *
 * Répond 202 : chaque journée coûte un appel au modèle, parfois trois quand
 * elle sort des tolérances. **Rien n'est enregistré** — c'est `savePlan` qui
 * écrit, une fois la proposition relue.
 */
export const generatePlan = (constraints: GenerateConstraints) =>
  api.post<MealPlanTask>('/meal-plans/generate/', constraints)

/** Ce que le frontend renvoie pour enregistrer une proposition. */
export interface PlanPayload {
  name: string
  notes?: string
  generated_by_ai: boolean
  days: {
    date: string
    entries: {
      meal_type_id: number
      entry_type: 'food' | 'recipe'
      food_id?: number
      recipe_id?: number
      new_recipe?: PlanProposal['days'][number]['meals'][number]['items'][number]['new_recipe']
      quantity: string
      unit_label: string
      generated_by_ai: boolean
    }[]
  }[]
}

export const savePlan = (payload: PlanPayload) => api.post<MealPlan>('/meal-plans/', payload)

export const deletePlan = (id: number) => api.delete<void>(`/meal-plans/${id}/`)

export const regenerateMeal = (id: number, payload: { day_id: number; meal_type_id: number }) =>
  api.post<MealPlanTask>(`/meal-plans/${id}/regenerate-entry/`, payload)

export interface AddToDiaryResult {
  entries: unknown[]
  skipped: string[]
  /** Repas déjà remplis : l'ajout attend confirmation (spec 01 §15). */
  conflicts: string[]
}

export const addPlanToDiary = (id: number, confirm = false) =>
  api.post<AddToDiaryResult>(`/meal-plans/${id}/add-to-diary/`, { confirm })

/** Transforme une proposition relue en ce que le backend enregistre. */
export function toPayload(proposal: PlanProposal, days: ProposalDay[]): PlanPayload {
  return {
    name: proposal.name,
    generated_by_ai: true,
    days: days.map((day) => ({
      date: day.date,
      entries: day.meals.flatMap((meal) =>
        meal.meal_type_id === null
          ? []
          : meal.items.map((item) => ({
              meal_type_id: meal.meal_type_id as number,
              entry_type: item.entry_type === 'recipe' ? ('recipe' as const) : ('food' as const),
              food_id: item.food?.id,
              recipe_id: item.recipe_id,
              new_recipe: item.new_recipe,
              quantity: item.quantity,
              unit_label: item.unit_label,
              generated_by_ai: true,
            })),
      ),
    })),
  }
}
