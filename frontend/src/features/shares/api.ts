import { api } from '@/lib/api/client'
import type {
  ChartSeries,
  DiaryDay,
  Paginated,
  SharePermission,
  ShareResourceType,
  ShareVisibility,
} from '@/lib/api/types'

export const sharesQueryKey = ['shares'] as const
export const receivedSharesQueryKey = ['shares', 'received'] as const
export const sharedDiaryQueryKey = (userId: number, date: string) =>
  ['shares', 'diary', userId, date] as const
export const sharedChartQueryKey = (userId: number, metric: string) =>
  ['shares', 'chart', userId, metric] as const

export interface SharePayload {
  resource_type: ShareResourceType
  resource_id?: number | null
  visibility: ShareVisibility
  target_user_id?: number | null
}

export const fetchShares = () => api.get<Paginated<SharePermission>>('/shares/')

export const fetchReceivedShares = () => api.get<Paginated<SharePermission>>('/shares/received/')

export const createShare = (payload: SharePayload) => api.post<SharePermission>('/shares/', payload)

export const revokeShare = (id: number) => api.delete<void>(`/shares/${id}/`)

/**
 * Consultation en lecture seule.
 *
 * Routes distinctes de celles du propriétaire : une route qui servirait
 * « mes données » ou « celles d'un autre » selon un paramètre est la façon
 * canonique de fabriquer un IDOR.
 */
export const fetchSharedDiary = (userId: number, date: string) =>
  api.get<DiaryDay>('/shared/diary/', { params: { user_id: userId, date } })

export const fetchSharedChart = (userId: number, metric: string, from: string, to: string) =>
  api.get<ChartSeries>('/shared/progress/charts/', {
    params: { user_id: userId, metric, from, to },
  })
