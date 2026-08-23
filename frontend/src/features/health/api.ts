import { api } from '@/lib/api/client'
import type { HealthStatus } from '@/lib/api/types'

export const healthQueryKey = ['health'] as const

export function fetchHealth(): Promise<HealthStatus> {
  return api.get<HealthStatus>('/health/')
}
