import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { diaryQueryKey } from '@/features/diary/api'
import { foodsQueryKey } from '@/features/foods/api'

import {
  addSavedMealToDiary,
  createSavedMeal,
  deleteSavedMeal,
  duplicateSavedMeal,
  fetchSavedMeals,
  savedMealsQueryKey,
  updateSavedMeal,
  type SavedMealPayload,
} from './api'

export function useSavedMeals() {
  return useQuery({ queryKey: savedMealsQueryKey, queryFn: fetchSavedMeals })
}

function useSavedMealInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: savedMealsQueryKey })
  }
}

export function useCreateSavedMeal() {
  const invalidate = useSavedMealInvalidation()

  return useMutation({
    mutationFn: (payload: SavedMealPayload) => createSavedMeal(payload),
    onSuccess: invalidate,
  })
}

export function useUpdateSavedMeal(id: number) {
  const invalidate = useSavedMealInvalidation()

  return useMutation({
    mutationFn: (payload: Partial<SavedMealPayload>) => updateSavedMeal(id, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteSavedMeal() {
  const invalidate = useSavedMealInvalidation()

  return useMutation({ mutationFn: (id: number) => deleteSavedMeal(id), onSuccess: invalidate })
}

export function useDuplicateSavedMeal() {
  const invalidate = useSavedMealInvalidation()

  return useMutation({ mutationFn: (id: number) => duplicateSavedMeal(id), onSuccess: invalidate })
}

export function useAddSavedMealToDiary() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number; date: string; meal_type_id: number }) =>
      addSavedMealToDiary(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: diaryQueryKey })
      void queryClient.invalidateQueries({ queryKey: foodsQueryKey })
    },
  })
}
