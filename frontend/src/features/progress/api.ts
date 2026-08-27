import { api } from '@/lib/api/client'
import type {
  BodyMeasurementEntry,
  ChartMetric,
  ChartSeries,
  Paginated,
  WeightEntry,
} from '@/lib/api/types'

export const progressQueryKey = ['progress'] as const
export const weightQueryKey = ['progress', 'weight'] as const
export const measurementsQueryKey = ['progress', 'measurements'] as const
export const chartQueryKey = (metric: ChartMetric, from: string, to: string) =>
  ['progress', 'charts', metric, from, to] as const

export const fetchWeightEntries = () => api.get<Paginated<WeightEntry>>('/progress/weight/')

/** Enregistre une pesée. Sur une date déjà pesée, l'API met à jour (spec 01 §19). */
export const saveWeight = (payload: { date: string; weight_kg: string; notes?: string | null }) =>
  api.post<WeightEntry>('/progress/weight/', payload)

export const deleteWeight = (id: number) => api.delete<void>(`/progress/weight/${id}/`)

export type MeasurementPayload = {
  date: string
} & Partial<
  Pick<
    BodyMeasurementEntry,
    'waist_cm' | 'hips_cm' | 'chest_cm' | 'arm_cm' | 'thigh_cm' | 'body_fat_percent' | 'notes'
  >
>

export const fetchMeasurements = () =>
  api.get<Paginated<BodyMeasurementEntry>>('/progress/measurements/')

export const saveMeasurement = (payload: MeasurementPayload) =>
  api.post<BodyMeasurementEntry>('/progress/measurements/', payload)

export const deleteMeasurement = (id: number) => api.delete<void>(`/progress/measurements/${id}/`)

/**
 * Série d'une métrique sur une période.
 *
 * Endpoint distinct de la liste des pesées, qui est paginée : une courbe
 * bâtie sur la première page serait tronquée sans le dire (spec 04 §14).
 */
export const fetchChart = (metric: ChartMetric, from: string, to: string) =>
  api.get<ChartSeries>('/progress/charts/', { params: { metric, from, to } })
