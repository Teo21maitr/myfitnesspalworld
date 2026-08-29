import type { PlanDay, ProposalDay } from '@/lib/api/types'

import type { DayItem, DayView } from './plan-day'

/** Une proposition est déjà groupée par repas : il n'y a rien à faire. */
export function fromProposal(day: ProposalDay): DayView {
  return {
    date: day.date,
    totals: day.totals,
    deviations: day.deviations,
    within_tolerance: day.within_tolerance,
    unmatched: day.unmatched,
    meals: day.meals.map((meal) => ({
      meal: meal.meal,
      meal_type_id: meal.meal_type_id,
      items: meal.items.map((item) => ({
        label: item.label,
        quantity: item.quantity,
        unit_label: item.unit_label,
        values: item.values,
        isNewRecipe: item.new_recipe !== undefined,
      })),
    })),
  }
}

/**
 * Une journée enregistrée arrive à plat : ses entrées se regroupent ici.
 *
 * L'ordre suit celui des repas de l'utilisateur, pas celui des entrées : c'est
 * ainsi qu'il lit son journal.
 */
export function fromPlan(day: PlanDay, meals: { id: number; name: string }[]): DayView {
  const grouped = meals
    .map((meal) => ({
      meal: meal.name,
      meal_type_id: meal.id,
      items: day.entries
        .filter((entry) => entry.meal_type === meal.id)
        .map((entry): DayItem => ({
          label: entry.label,
          quantity: entry.quantity,
          unit_label: entry.unit_label,
          values: entry.values,
        })),
    }))
    .filter((meal) => meal.items.length > 0)

  return {
    date: day.date,
    totals: day.totals,
    deviations: day.deviations,
    within_tolerance: day.within_tolerance,
    meals: grouped,
  }
}
