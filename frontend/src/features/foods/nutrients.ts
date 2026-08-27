import type { FoodNutrition } from '@/lib/api/types'

export interface Row {
  label: string
  key: keyof FoodNutrition
  unit: string
}

export const MACROS: Row[] = [
  { label: 'Énergie', key: 'energy_kcal', unit: 'kcal' },
  { label: 'Protéines', key: 'protein_g', unit: 'g' },
  { label: 'Glucides', key: 'carbohydrates_g', unit: 'g' },
  { label: 'dont sucres', key: 'sugars_g', unit: 'g' },
  { label: 'Lipides', key: 'fat_g', unit: 'g' },
  { label: 'Fibres', key: 'fiber_g', unit: 'g' },
  { label: 'Glucides nets', key: 'net_carbs_g', unit: 'g' },
]

export const MICROS: Row[] = [
  { label: 'Sel', key: 'salt_g', unit: 'g' },
  { label: 'Sodium', key: 'sodium_mg', unit: 'mg' },
  { label: 'Cholestérol', key: 'cholesterol_mg', unit: 'mg' },
  { label: 'Potassium', key: 'potassium_mg', unit: 'mg' },
  { label: 'Calcium', key: 'calcium_mg', unit: 'mg' },
  { label: 'Fer', key: 'iron_mg', unit: 'mg' },
  { label: 'Magnésium', key: 'magnesium_mg', unit: 'mg' },
  { label: 'Vitamine A', key: 'vitamin_a_ug', unit: 'µg' },
  { label: 'Vitamine B6', key: 'vitamin_b6_mg', unit: 'mg' },
  { label: 'Vitamine B12', key: 'vitamin_b12_ug', unit: 'µg' },
  { label: 'Vitamine C', key: 'vitamin_c_mg', unit: 'mg' },
  { label: 'Vitamine D', key: 'vitamin_d_ug', unit: 'µg' },
  { label: 'Vitamine E', key: 'vitamin_e_mg', unit: 'mg' },
  { label: 'Vitamine K', key: 'vitamin_k_ug', unit: 'µg' },
]

/**
 * Libellé de chaque nutriment, pour nommer ceux dont le total est partiel
 * plutôt que d'annoncer un décompte anonyme.
 */
export const NUTRIENT_LABELS: Record<string, string> = Object.fromEntries(
  [...MACROS, ...MICROS].map((row) => [row.key, row.label]),
)
