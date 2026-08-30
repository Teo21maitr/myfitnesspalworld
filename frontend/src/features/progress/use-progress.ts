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
import {
  deletePhoto,
  deletePhotoGroup,
  fetchPhotoGroups,
  photosQueryKey,
  uploadPhotos,
} from './photos'

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

export function usePhotoGroups() {
  return useQuery({ queryKey: photosQueryKey, queryFn: fetchPhotoGroups })
}

export function useUploadPhotos() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: uploadPhotos,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: photosQueryKey })
    },
  })
}

/**
 * Suppression d'un groupe ou d'une seule photo.
 *
 * Elle est **définitive** des deux côtés : la ligne part, et le fichier avec
 * elle (spec 01 §20). L'écran doit le dire avant, pas après.
 */
export function useDeletePhotoGroup() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deletePhotoGroup,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: photosQueryKey })
    },
  })
}

export function useDeletePhoto() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ groupId, photoId }: { groupId: number; photoId: number }) =>
      deletePhoto(groupId, photoId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: photosQueryKey })
    },
  })
}
