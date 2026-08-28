import type { LabelNutrient } from '@/lib/api/types'

/** Nom lisible de chaque nutriment lu sur une étiquette. */
export const NUTRIENT_LABELS: Record<LabelNutrient, string> = {
  energy_kcal: 'énergie',
  protein_g: 'protéines',
  carbohydrates_g: 'glucides',
  sugars_g: 'sucres',
  fat_g: 'lipides',
  fiber_g: 'fibres',
  salt_g: 'sel',
  sodium_mg: 'sodium',
}

/**
 * Énumère ce que la photo n'a pas donné.
 *
 * Nommer les manques plutôt que laisser des champs vides sans explication :
 * un champ vide peut passer pour un oubli de saisie, alors qu'il dit « la
 * photo ne le montrait pas » (spec 01 §8).
 */
export function describeUnreadable(nutrients: LabelNutrient[]): string {
  const names = nutrients.map((nutrient) => NUTRIENT_LABELS[nutrient] ?? nutrient)
  if (names.length === 0) return ''
  if (names.length === 1) return names[0] as string

  return `${names.slice(0, -1).join(', ')} et ${names.at(-1)}`
}
