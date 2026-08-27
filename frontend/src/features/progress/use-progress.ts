import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { diaryQueryKey } from '@/features/diary/api'
import type { ChartMetric } from '@/lib/api/types'

import {
  chartQueryKey,
  deleteMeasurement,
  deleteWeight,
  fetchChart,
  fetchMeasurements,
  fetchWeightEntries,
  measurementsQueryKey,
  progressQueryKey,
  saveMeasurement,
  saveWeight,
  weightQueryKey,
  type MeasurementPayload,
} from './api'

export function useWeightEntries() {
  return useQuery({ queryKey: weightQueryKey, queryFn: fetchWeightEntries })
}

export function useMeasurements() {
  return useQuery({ queryKey: measurementsQueryKey, queryFn: fetchMeasurements })
}

export function useChart(metric: ChartMetric, from: string, to: string) {
  return useQuery({
    queryKey: chartQueryKey(metric, from, to),
    queryFn: () => fetchChart(metric, from, to),
  })
}

/**
 * Invalide la progression et le journal.
 *
 * Le tableau de bord affiche la dernière pesée : la laisser en cache
 * montrerait un poids périmé sur l'accueil juste après la saisie.
 */
function useProgressInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: progressQueryKey })
    void queryClient.invalidateQueries({ queryKey: diaryQueryKey })
  }
}

export function useSaveWeight() {
  const invalidate = useProgressInvalidation()

  return useMutation({
    mutationFn: (payload: { date: string; weight_kg: string; notes?: string | null }) =>
      saveWeight(payload),
    onSuccess: invalidate,
  })
}

export function useDeleteWeight() {
  const invalidate = useProgressInvalidation()

  return useMutation({ mutationFn: (id: number) => deleteWeight(id), onSuccess: invalidate })
}

export function useSaveMeasurement() {
  const invalidate = useProgressInvalidation()

  return useMutation({
    mutationFn: (payload: MeasurementPayload) => saveMeasurement(payload),
    onSuccess: invalidate,
  })
}

export function useDeleteMeasurement() {
  const invalidate = useProgressInvalidation()

  return useMutation({ mutationFn: (id: number) => deleteMeasurement(id), onSuccess: invalidate })
}
