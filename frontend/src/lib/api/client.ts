import type { ApiErrorPayload } from './types'

/**
 * Client HTTP de l'API.
 *
 * Les cookies d'authentification sont HttpOnly : le navigateur les envoie
 * automatiquement grâce à `credentials: 'include'` et le frontend n'y a jamais
 * accès (spec 05 §5).
 */

/**
 * Adresse de l'API, **relative** par défaut.
 *
 * L'application et l'API partagent une origine : nginx relaie `/api/` en
 * production, Vite fait de même en développement. Un chemin relatif est donc
 * juste partout, et ne peut plus figer l'adresse d'une machine dans le bundle.
 * Une URL absolue reste acceptée, pour un déploiement sans relais.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

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
  /**
   * Réponse rendue en `Blob` plutôt que parsée.
   *
   * Nécessaire aux exports : lire un PDF comme du texte le corromprait
   * (spec 04 §17). Les erreurs restent traitées normalement, le backend
   * répondant alors du JSON.
   */
  blob?: boolean
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const base = API_BASE_URL.replace(/\/$/, '')
  // L'origine sert de base aux adresses relatives ; elle est ignorée quand
  // `API_BASE_URL` est absolue.
  const url = new URL(`${base}/${path.replace(/^\//, '')}`, window.location.origin)

  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

/** Exécute la requête et convertit les échecs en `ApiError` / `NetworkError`. */
async function performRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const { json, params, headers, blob, ...init } = options
  const method = (init.method ?? 'GET').toUpperCase()

  const requestHeaders = new Headers(headers)
  requestHeaders.set('Accept', 'application/json')

  if (json !== undefined) {
    requestHeaders.set('Content-Type', 'application/json')
  }

  // Django exige l'en-tête CSRF sur les méthodes non idempotentes.
  if (UNSAFE_METHODS.has(method)) {
    const token = currentCsrfToken()
    if (token) {
      requestHeaders.set('X-CSRFToken', token)
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

  if (blob && response.ok) {
    return (await response.blob()) as T
  }

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

/**
 * Passe à `true` dès qu'un renouvellement échoue.
 *
 * Sans ce garde-fou, chaque page consultée hors session relancerait un
 * renouvellement voué à l'échec et consommerait inutilement le quota de
 * l'API. Il est levé dès qu'une session valide est établie.
 */
let refreshKnownToFail = false

/** Signale qu'une session valide existe de nouveau (connexion réussie). */
export function resetSessionRefresh(): void {
  refreshKnownToFail = false
}

function refreshSession(): Promise<unknown> {
  refreshPromise ??= performRequest('/auth/refresh/', { method: 'POST' })
    .then((result) => {
      refreshKnownToFail = false
      return result
    })
    .catch((error: unknown) => {
      refreshKnownToFail = true
      throw error
    })
    .finally(() => {
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

/**
 * Jeton CSRF conservé en mémoire.
 *
 * Le cookie ne suffit pas quand l'API vit sur un autre domaine que
 * l'application : `document.cookie` ne donne accès qu'aux cookies du domaine
 * courant. Le navigateur envoie bien celui de l'API à chaque requête — le
 * serveur le voit — mais nous ne pouvons pas le lire pour le recopier dans
 * l'en-tête. `/auth/csrf/` rend donc aussi le jeton dans son corps.
 *
 * En mémoire seulement : un rechargement le redemande, et rien n'en subsiste
 * sur le disque (spec 05 §5).
 */
let csrfToken: string | null = null

/** Oublie le jeton conservé. Employé par les tests, et au changement de session. */
export function resetCsrfToken(): void {
  csrfToken = null
}

/** Le cookie s'il est lisible — même domaine —, sinon le jeton rapatrié. */
function currentCsrfToken(): string | null {
  return readCookie(CSRF_COOKIE_NAME) ?? csrfToken
}

/** Amorce le jeton CSRF avant la première écriture de la session. */
async function ensureCsrfToken(): Promise<void> {
  if (currentCsrfToken()) return

  try {
    const { csrf_token } = await performRequest<{ csrf_token: string }>('/auth/csrf/', {
      method: 'GET',
    })
    csrfToken = csrf_token
  } catch {
    // L'absence de jeton se manifestera par une 403 explicite, plus parlante
    // qu'un échec silencieux ici.
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()

  if (UNSAFE_METHODS.has(method)) {
    await ensureCsrfToken()
  }

  try {
    return await performRequest<T>(path, options)
  } catch (error) {
    const isAuthRoute = AUTH_PATHS.some((authPath) => path.startsWith(authPath))

    // Un jeton périmé — cookie effacé ailleurs, session repartie — rendrait
    // toute écriture impossible jusqu'au rechargement de la page. Un seul
    // rejeu, avec un jeton neuf. Le code distingue ce cas d'un vrai refus
    // d'accès, qu'aucun rejeu ne réparerait.
    if (error instanceof ApiError && error.code === 'csrf_failed') {
      csrfToken = null
      await ensureCsrfToken()
      return performRequest<T>(path, options)
    }

    if (!(error instanceof ApiError) || !error.isUnauthorized || isAuthRoute) {
      throw error
    }

    // Inutile de réessayer si le renouvellement a déjà échoué : l'utilisateur
    // n'a tout simplement pas de session.
    if (refreshKnownToFail) {
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
  /** POST rendant un fichier binaire (exports CSV et PDF). */
  download: (path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<Blob>(path, { ...options, method: 'POST', json, blob: true }),
}
