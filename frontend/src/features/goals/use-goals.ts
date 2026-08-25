import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createGoal,
  currentGoalQueryKey,
  deleteDayOverride,
  fetchCurrentGoal,
  fetchGoals,
  goalsQueryKey,
  setDayOverride,
  updateGoal,
  type GoalPayload,
} from '@/features/nutrition/api'
import { ApiError } from '@/lib/api/client'
import type { CurrentGoal, DayOverride } from '@/lib/api/types'

/** Objectif applicable aujourd'hui, surcharge de jour comprise. */
export function useCurrentGoal() {
  return useQuery<CurrentGoal | null>({
    queryKey: currentGoalQueryKey,
    queryFn: async () => {
      try {
        return await fetchCurrentGoal()
      } catch (error) {
        // Aucun objectif défini n'est pas une erreur à signaler.
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
    retry: false,
  })
}

/** Historique complet, du plus récent au plus ancien. */
export function useGoalHistory() {
  return useQuery({ queryKey: goalsQueryKey, queryFn: fetchGoals })
}

function useGoalInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: goalsQueryKey })
    queryClient.invalidateQueries({ queryKey: currentGoalQueryKey })
  }
}

export function useUpdateGoal(goalId: number) {
  const invalidate = useGoalInvalidation()

  return useMutation({
    mutationFn: (payload: Partial<GoalPayload>) => updateGoal(goalId, payload),
    onSuccess: invalidate,
  })
}

export function useCreateGoal() {
  const invalidate = useGoalInvalidation()

  return useMutation({ mutationFn: createGoal, onSuccess: invalidate })
}

type OverrideValues = Partial<Omit<DayOverride, 'id' | 'weekday' | 'weekday_label'>>

export function useSetDayOverride(goalId: number) {
  const invalidate = useGoalInvalidation()

  return useMutation({
    mutationFn: ({ weekday, values }: { weekday: number; values: OverrideValues }) =>
      setDayOverride(goalId, weekday, values),
    onSuccess: invalidate,
  })
}

export function useDeleteDayOverride(goalId: number) {
  const invalidate = useGoalInvalidation()

  return useMutation({
    mutationFn: (weekday: number) => deleteDayOverride(goalId, weekday),
    onSuccess: invalidate,
  })
}
