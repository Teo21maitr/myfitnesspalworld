import { useQuery } from '@tanstack/react-query'

import type { AsyncTask } from '@/lib/api/types'

import { fetchTask, taskQueryKey } from './api'

/** Intervalle d'interrogation pendant le traitement. */
export const POLL_INTERVAL_MS = 1500

/** Au-delà, on cesse d'attendre : le worker ne répondra plus. */
export const POLL_TIMEOUT_MS = 90_000

export function isRunning(task: AsyncTask<unknown> | undefined): boolean {
  return task?.status === 'pending' || task?.status === 'processing'
}

/**
 * Suit une tâche jusqu'à son terme.
 *
 * L'interrogation s'arrête d'elle-même dès que la tâche aboutit ou échoue :
 * continuer à interroger une tâche terminée n'apprendrait plus rien.
 */
export function useAsyncTask<TResult>(taskId: string | null) {
  return useQuery({
    queryKey: taskQueryKey(taskId ?? ''),
    queryFn: () => fetchTask<TResult>(taskId as string),
    enabled: Boolean(taskId),
    refetchInterval: (query) => (isRunning(query.state.data) ? POLL_INTERVAL_MS : false),
    // Une tâche déjà lue ne change plus : inutile de la relire au retour sur
    // l'onglet.
    refetchOnWindowFocus: false,
    gcTime: POLL_TIMEOUT_MS,
  })
}
