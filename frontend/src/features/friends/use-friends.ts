import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { foodsQueryKey } from '@/features/foods/api'
import { recipesQueryKey } from '@/features/recipes/api'
import { sharesQueryKey } from '@/features/shares/api'

import {
  acceptFriendRequest,
  fetchFriendRequests,
  fetchFriends,
  friendRequestsQueryKey,
  friendsQueryKey,
  rejectFriendRequest,
  removeFriend,
  searchUsers,
  sendFriendRequest,
  userSearchQueryKey,
} from './api'

/** La recherche ne se déclenche qu'à partir de deux caractères (spec 01 §17). */
export const MINIMUM_QUERY_LENGTH = 2

export function useUserSearch(query: string) {
  const trimmed = query.trim()

  return useQuery({
    queryKey: userSearchQueryKey(trimmed),
    queryFn: () => searchUsers(trimmed),
    enabled: trimmed.length >= MINIMUM_QUERY_LENGTH,
    staleTime: 60_000,
  })
}

export function useFriends() {
  return useQuery({ queryKey: friendsQueryKey, queryFn: fetchFriends })
}

export function useFriendRequests() {
  return useQuery({ queryKey: friendRequestsQueryKey, queryFn: fetchFriendRequests })
}

/** Nombre de demandes reçues en attente, pour la pastille de navigation. */
export function usePendingRequestCount(): number {
  const { data } = useFriendRequests()
  const rows = Array.isArray(data?.results) ? data.results : []

  return rows.filter((request) => request.direction === 'received').length
}

/**
 * Invalide le social **et** les ressources partageables.
 *
 * Retirer un ami révoque les partages qui le visaient : les listes d'aliments
 * et de recettes changent au même instant, et les laisser en cache montrerait
 * des ressources auxquelles on n'a plus accès.
 */
function useSocialInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: friendsQueryKey })
    void queryClient.invalidateQueries({ queryKey: sharesQueryKey })
    void queryClient.invalidateQueries({ queryKey: recipesQueryKey })
    void queryClient.invalidateQueries({ queryKey: foodsQueryKey })
  }
}

export function useSendFriendRequest() {
  const invalidate = useSocialInvalidation()

  return useMutation({
    mutationFn: (userId: number) => sendFriendRequest(userId),
    onSuccess: invalidate,
  })
}

export function useAnswerFriendRequest() {
  const invalidate = useSocialInvalidation()

  return useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) =>
      accept ? acceptFriendRequest(id) : rejectFriendRequest(id),
    onSuccess: invalidate,
  })
}

export function useRemoveFriend() {
  const invalidate = useSocialInvalidation()

  return useMutation({
    mutationFn: (userId: number) => removeFriend(userId),
    onSuccess: invalidate,
  })
}
