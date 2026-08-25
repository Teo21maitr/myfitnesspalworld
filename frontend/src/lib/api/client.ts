import type { ApiErrorPayload } from './types'

/**
 * Client HTTP de l'API.
 *
 * Les cookies d'authentification sont HttpOnly : le navigateur les envoie
 * automatiquement grâce à `credentials: 'include'` et le frontend n'y a jamais
 * accès (spec 05 §5).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001/api/v1'

const CSRF_COOKIE_NAME = 'mfp_csrftoken'
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/** Routes qui ne doivent jamais déclencher de rafraîchissement de session. */
const AUTH_PATHS = [
  '/auth/login/',
  '/auth/logout/',
  '/auth/refresh/',
  '/auth/csrf/',
  '/auth/register-request/',
  '/auth/forgot-password/',
  '/auth/reset-password/',
]

/** Erreur d'API portant le format normalisé du backend. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly errors: Record<string, string[]>

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code
    this.errors = payload.errors
  }

  /** Première erreur associée à un champ de formulaire, s'il y en a une. */
  fieldError(field: string): string | undefined {
    return this.errors[field]?.[0]
  }

  /** Erreur d'authentification : la session est absente ou expirée. */
  get isUnauthorized(): boolean {
    return this.status === 401
  }
}

/** Erreur réseau : le backend n'a pas pu être joint (hors ligne, DNS, CORS). */
export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('Impossible de joindre le serveur. Vérifiez votre connexion.')
    this.name = 'NetworkError'
    this.cause = cause
  }
}

function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.split('=')[1]
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    'message' in value &&
    typeof (value as ApiErrorPayload).message === 'string'
  )
}

export interface RequestOptions extends RequestInit {
  /** Corps sérialisé en JSON. Utiliser `body` directement pour un FormData. */
  json?: unknown
  /** Paramètres de requête ajoutés à l'URL. */
  params?: Record<string, string | number | boolean | undefined>
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const base = API_BASE_URL.replace(/\/$/, '')
  const url = new URL(`${base}/${path.replace(/^\//, '')}`)

  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

/** Exécute la requête et convertit les échecs en `ApiError` / `NetworkError`. */
async function performRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const { json, params, headers, ...init } = options
  const method = (init.method ?? 'GET').toUpperCase()

  const requestHeaders = new Headers(headers)
  requestHeaders.set('Accept', 'application/json')

  if (json !== undefined) {
    requestHeaders.set('Content-Type', 'application/json')
  }

  // Django exige l'en-tête CSRF sur les méthodes non idempotentes.
  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME)
    if (csrfToken) {
      requestHeaders.set('X-CSRFToken', csrfToken)
    }
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, params), {
      ...init,
      method,
      headers: requestHeaders,
      credentials: 'include',
      body: json !== undefined ? JSON.stringify(json) : init.body,
    })
  } catch (cause) {
    throw new NetworkError(cause)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const isJson = response.headers.get('Content-Type')?.includes('application/json') ?? false
  const payload: unknown = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    throw new ApiError(
      response.status,
      isApiErrorPayload(payload)
        ? payload
        : {
            code: 'http_error',
            message: `Erreur ${response.status}.`,
            errors: {},
          },
    )
  }

  return payload as T
}

/**
 * Rafraîchissement silencieux de la session.
 *
 * Les appels concurrents partagent la même promesse : une seule rotation de
 * token est déclenchée même si plusieurs requêtes échouent en même temps.
 */
let refreshPromise: Promise<unknown> | null = null

function refreshSession(): Promise<unknown> {
  refreshPromise ??= performRequest('/auth/refresh/', { method: 'POST' }).finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** Enregistre l'action à exécuter quand la session est définitivement perdue. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler
}

/** Amorce le cookie CSRF avant la première écriture de la session. */
async function ensureCsrfCookie(): Promise<void> {
  if (readCookie(CSRF_COOKIE_NAME)) return

  try {
    await performRequest('/auth/csrf/', { method: 'GET' })
  } catch {
    // L'absence de cookie CSRF se manifestera par une 403 explicite, plus
    // parlante qu'un échec silencieux ici.
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()

  if (UNSAFE_METHODS.has(method)) {
    await ensureCsrfCookie()
  }

  try {
    return await performRequest<T>(path, options)
  } catch (error) {
    const isAuthRoute = AUTH_PATHS.some((authPath) => path.startsWith(authPath))

    if (!(error instanceof ApiError) || !error.isUnauthorized || isAuthRoute) {
      throw error
    }

    // L'access token a expiré : une seule tentative de renouvellement, puis un
    // unique rejeu de la requête d'origine.
    try {
      await refreshSession()
    } catch {
      onUnauthorized?.()
      throw error
    }

    return performRequest<T>(path, options)
  }
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'POST', json }),
  put: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PUT', json }),
  patch: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', json }),
  delete: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'DELETE', json }),
}
