import { api } from '@/lib/api/client'
import type { AsyncTask } from '@/lib/api/types'

export const taskQueryKey = (id: string) => ['tasks', id] as const

/** État d'un traitement long (spec 04 §9). */
export const fetchTask = <TResult>(id: string) => api.get<AsyncTask<TResult>>(`/tasks/${id}/`)
