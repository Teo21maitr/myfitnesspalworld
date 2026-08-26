import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { foodsQueryKey } from '@/features/foods/api'

import {
  createEntry,
  deleteEntry,
  diaryDayQueryKey,
  diaryQueryKey,
  fetchDiaryDay,
  fetchMealTypes,
  mealTypesQueryKey,
  updateEntry,
  type EntryUpdate,
  type FoodEntryPayload,
  type QuickAddPayload,
} from './api'

export function useDiaryDay(date: string) {
  return useQuery({ queryKey: diaryDayQueryKey(date), queryFn: () => fetchDiaryDay(date) })
}

export function useMealTypes() {
  return useQuery({ queryKey: mealTypesQueryKey, queryFn: fetchMealTypes, staleTime: 5 * 60_000 })
}

/**
 * Invalide le journal et les listes d'aliments.
 *
 * Journaliser un aliment met à jour ses compteurs d'usage : les onglets
 * « récents » et « fréquents » doivent être rechargés, sans quoi ils
 * afficheraient un état périmé.
 */
function useDiaryInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: diaryQueryKey })
    void queryClient.invalidateQueries({ queryKey: foodsQueryKey })
  }
}

export function useCreateEntry() {
  const invalidate = useDiaryInvalidation()

  return useMutation({
    mutationFn: (payload: FoodEntryPayload | QuickAddPayload) => createEntry(payload),
    onSuccess: invalidate,
  })
}

export function useUpdateEntry() {
  const invalidate = useDiaryInvalidation()

  return useMutation({
    mutationFn: ({ id, ...payload }: EntryUpdate & { id: number }) => updateEntry(id, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteEntry() {
  const invalidate = useDiaryInvalidation()

  return useMutation({ mutationFn: deleteEntry, onSuccess: invalidate })
}
