import { shift, today } from '@/features/diary/dates'

/** Périodes proposées, alignées sur la spec 01 §21 : jour, semaine, mois. */
export const PERIOD_OPTIONS = [
  { value: '1', label: 'Aujourd’hui' },
  { value: '7', label: '7 derniers jours' },
  { value: '30', label: '30 derniers jours' },
  { value: '90', label: '90 derniers jours' },
] as const

export const DEFAULT_PERIOD = '30'

/** Bornes d'une période exprimée en nombre de jours, bornes comprises. */
export function periodRange(days: string): { from: string; to: string } {
  const to = today()
  const count = Number(days)
  // Une valeur inattendue retombe sur un jour plutôt que sur `NaN`, qui
  // produirait une date invalide et une requête refusée.
  const span = Number.isFinite(count) && count > 0 ? count : 1
  return { from: shift(to, -(span - 1)), to }
}
