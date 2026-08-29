import type { ChartMetric } from '@/lib/api/types'

/**
 * Les métriques traçables (spec 04 §14).
 *
 * Une seule liste, partagée par ma progression et celle d'un ami : deux listes
 * divergeraient, et l'écran partagé n'en montrerait qu'une partie — ce qu'il
 * faisait, figé sur le poids alors que l'API en sert sept.
 */
export const METRIC_OPTIONS: readonly { value: ChartMetric; label: string }[] = [
  { value: 'weight', label: 'Poids' },
  { value: 'waist', label: 'Tour de taille' },
  { value: 'hips', label: 'Tour de hanches' },
  { value: 'chest', label: 'Tour de poitrine' },
  { value: 'arm', label: 'Tour de bras' },
  { value: 'thigh', label: 'Tour de cuisse' },
  { value: 'body_fat', label: 'Masse grasse' },
] as const

export function metricLabel(metric: ChartMetric): string {
  return METRIC_OPTIONS.find((option) => option.value === metric)?.label ?? 'Progression'
}
