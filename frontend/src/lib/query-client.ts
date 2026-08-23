import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { ApiError, NetworkError } from './api/client'

/** Message utilisateur compréhensible pour n'importe quelle erreur (spec 10 §12). */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof NetworkError) {
    return error.message
  }
  return 'Une erreur inattendue est survenue.'
}

/** Ne pas insister sur une erreur définitive côté client (4xx). */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false
  }
  return failureCount < 2
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
    // Gestion globale des erreurs : toute requête ou mutation en échec
    // remonte un message à l'utilisateur.
    queryCache: new QueryCache({
      onError: (error) => toast.error(describeError(error)),
    }),
    mutationCache: new MutationCache({
      onError: (error) => toast.error(describeError(error)),
    }),
  })
}
