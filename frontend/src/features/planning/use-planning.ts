import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAsyncTask } from '@/features/tasks/use-task'
import type { PlanProposal } from '@/lib/api/types'

import {
  addPlanToDiary,
  deletePlan,
  fetchPlan,
  fetchPlans,
  generatePlan,
  planQueryKey,
  plansQueryKey,
  regenerateMeal,
  savePlan,
  type GenerateConstraints,
  type PlanPayload,
} from './api'

export function usePlans() {
  return useQuery({ queryKey: plansQueryKey, queryFn: fetchPlans })
}

export function usePlan(id: number) {
  return useQuery({
    queryKey: planQueryKey(id),
    queryFn: () => fetchPlan(id),
    enabled: Number.isFinite(id),
  })
}

export function useGeneratePlan() {
  return useMutation({
    mutationFn: (constraints: GenerateConstraints) => generatePlan(constraints),
  })
}

/** Suit la composition d'une proposition, journée après journée. */
export function usePlanProposalTask(taskId: string | null) {
  return useAsyncTask<PlanProposal>(taskId)
}

function useInvalidation() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: plansQueryKey })
}

export function useSavePlan() {
  const invalidate = useInvalidation()

  return useMutation({
    mutationFn: (payload: PlanPayload) => savePlan(payload),
    onSuccess: invalidate,
  })
}

export function useDeletePlan() {
  const invalidate = useInvalidation()

  return useMutation({ mutationFn: (id: number) => deletePlan(id), onSuccess: invalidate })
}

export function useRegenerateMeal(planId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { day_id: number; meal_type_id: number }) =>
      regenerateMeal(planId, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: planQueryKey(planId) }),
  })
}

export function useAddPlanToDiary(planId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (confirm: boolean) => addPlanToDiary(planId, confirm),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['diary'] }),
  })
}
