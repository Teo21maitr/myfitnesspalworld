import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'

import { ApiError } from '@/lib/api/client'
import type { AuthUser } from '@/lib/api/types'

import { fetchMe, meQueryKey } from './api'

/**
 * Charge le compte courant au démarrage de l'application.
 *
 * Une 401 signifie simplement « pas connecté » : elle ne doit ni être
 * réessayée, ni remonter comme une erreur à l'utilisateur.
 */
export function useMe(): UseQueryResult<AuthUser | null> {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async () => {
      try {
        return await fetchMe()
      } catch (error) {
        if (error instanceof ApiError && error.isUnauthorized) {
          return null
        }
        throw error
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}

/** Efface l'état d'authentification côté client. */
export function useClearSession(): () => void {
  const queryClient = useQueryClient()

  return () => {
    queryClient.setQueryData(meQueryKey, null)
    queryClient.clear()
    queryClient.setQueryData(meQueryKey, null)
  }
}
