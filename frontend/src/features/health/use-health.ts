import { useQuery } from '@tanstack/react-query'

import { fetchHealth, healthQueryKey } from './api'

/** Interroge l'état du backend (base de données et cache). */
export function useHealth() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: fetchHealth,
    staleTime: 10_000,
  })
}
