import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api/client'
import type { AIStatus } from '@/lib/api/types'

export const aiStatusQueryKey = ['ai', 'status'] as const

/**
 * L'IA est-elle disponible ?
 *
 * Interrogée à l'ouverture d'un écran qui en dépend : apprendre qu'une
 * fonctionnalité est éteinte après avoir cadré sa photo est une mauvaise façon
 * de l'apprendre.
 */
export const fetchAIStatus = () => api.get<AIStatus>('/ai/status/')

/**
 * Un échec de cette requête ne doit pas condamner l'écran : la prise de vue
 * reste offerte et l'indisponibilité, si elle est réelle, ressortira au moment
 * de l'envoi.
 */
export function useAIStatus() {
  return useQuery({
    queryKey: aiStatusQueryKey,
    queryFn: fetchAIStatus,
    // Un coupe-circuit administrateur peut basculer pendant la session.
    staleTime: 60_000,
    retry: false,
  })
}

/** Message affiché quand l'IA est coupée, non configurée ou en panne. */
export const AI_DISABLED_MESSAGE =
  'L’analyse par IA est indisponible pour le moment. Le reste de l’application fonctionne normalement : vous pouvez ajouter vos aliments par la recherche.'
