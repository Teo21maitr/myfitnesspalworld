import type { MealType } from '@/lib/api/types'

/**
 * Choix du repas proposé par défaut.
 *
 * Retenir systématiquement le premier repas de la liste revenait à proposer
 * « Petit-déjeuner » à toute heure : un dîner scanné à 20 h partait au
 * petit-déjeuner dès que l'utilisateur ne remarquait pas le sélecteur.
 *
 * La proposition suit donc l'heure. Elle s'appuie sur `system_key` et non sur
 * le nom, qui est renommable : un repas rebaptisé « Souper » reste le dîner.
 */

/** Plages horaires des repas système, en heures locales. */
const SCHEDULE: readonly { key: string; from: number; to: number }[] = [
  { key: 'breakfast', from: 5, to: 11 },
  { key: 'lunch', from: 11, to: 15 },
  { key: 'dinner', from: 18, to: 23 },
]

/** Hors de ces plages — milieu d'après-midi, fin de soirée — c'est une collation. */
const FALLBACK_KEY = 'snacks'

export function activeMeals(meals: MealType[] | undefined): MealType[] {
  // `Array.isArray` plutôt qu'un simple `??` : une réponse de forme inattendue
  // doit dégrader l'écran, pas le faire tomber.
  return (Array.isArray(meals) ? meals : []).filter((meal) => meal.is_active)
}

function keyForHour(hour: number): string {
  return SCHEDULE.find((slot) => hour >= slot.from && hour < slot.to)?.key ?? FALLBACK_KEY
}

/**
 * Identifiant du repas à proposer, ou chaîne vide s'il n'y en a aucun.
 *
 * Un repas système désactivé fait retomber sur le premier repas actif : mieux
 * vaut une proposition imparfaite qu'un formulaire qu'on ne peut pas valider.
 */
export function defaultMealTypeId(meals: MealType[], now: Date = new Date()): string {
  const active = activeMeals(meals)
  if (active.length === 0) return ''

  const wanted = keyForHour(now.getHours())
  const match = active.find((meal) => meal.system_key === wanted)

  return String((match ?? active[0])?.id ?? '')
}
