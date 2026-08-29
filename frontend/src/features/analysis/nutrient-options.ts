import { MACROS, MICROS } from '@/features/foods/nutrients'

/**
 * Nutriments analysables.
 *
 * `net_carbs_g` est écarté : c'est une soustraction d'affichage, pas une
 * colonne du référentiel — le backend refuserait la demande.
 */
export const NUTRIENT_OPTIONS = [...MACROS, ...MICROS]
  .filter((row) => row.key !== 'net_carbs_g')
  .map((row) => ({ value: row.key as string, label: row.label }))

export const DEFAULT_NUTRIENT = 'energy_kcal'
