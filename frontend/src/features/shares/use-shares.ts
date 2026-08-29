import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { foodsQueryKey } from '@/features/foods/api'
import { recipesQueryKey } from '@/features/recipes/api'

import {
  createShare,
  fetchReceivedShares,
  fetchShares,
  fetchSharedChart,
  fetchSharedDiary,
  receivedSharesQueryKey,
  revokeShare,
  sharedChartQueryKey,
  sharedDiaryQueryKey,
  sharesQueryKey,
  type SharePayload,
} from './api'

export function useShares() {
  return useQuery({ queryKey: sharesQueryKey, queryFn: fetchShares })
}

export function useReceivedShares() {
  return useQuery({ queryKey: receivedSharesQueryKey, queryFn: fetchReceivedShares })
}

export function useSharedDiary(userId: number, date: string) {
  return useQuery({
    queryKey: sharedDiaryQueryKey(userId, date),
    queryFn: () => fetchSharedDiary(userId, date),
    enabled: Number.isFinite(userId),
  })
}

export function useSharedChart(userId: number, metric: string, from: string, to: string) {
  return useQuery({
    queryKey: sharedChartQueryKey(userId, metric, from, to),
    queryFn: () => fetchSharedChart(userId, metric, from, to),
    enabled: Number.isFinite(userId),
  })
}

function useShareInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: sharesQueryKey })
    // Partager ou révoquer change ce que les autres voient, mais aussi ce que
    // les listes locales affichent comme état de partage.
    void queryClient.invalidateQueries({ queryKey: recipesQueryKey })
    void queryClient.invalidateQueries({ queryKey: foodsQueryKey })
  }
}

export function useCreateShare() {
  const invalidate = useShareInvalidation()

  return useMutation({
    mutationFn: (payload: SharePayload) => createShare(payload),
    onSuccess: invalidate,
  })
}

export function useRevokeShare() {
  const invalidate = useShareInvalidation()

  return useMutation({ mutationFn: (id: number) => revokeShare(id), onSuccess: invalidate })
}
