/** Format d'erreur normalisé renvoyé par l'API (spec 10 §5). */
export interface ApiErrorPayload {
  code: string
  message: string
  errors: Record<string, string[]>
}

/** Enveloppe de pagination `page` / `limit` (spec 04). */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  version: string
  time: string
  checks: {
    database: 'ok' | 'error'
    cache: 'ok' | 'error'
  }
}
