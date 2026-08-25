import { vi } from 'vitest'

export const CSRF_COOKIE = 'mfp_csrftoken'

/** Réponse JSON prête à l'emploi. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export interface RouteStub {
  /** Fragment d'URL identifiant la route. */
  match: string
  /** Réponse produite à chaque appel — une fonction pour éviter tout corps déjà lu. */
  respond: () => Response
}

/**
 * Remplace `fetch` par un routeur de test.
 *
 * Chaque appel produit une nouvelle `Response` : le client peut enchaîner
 * plusieurs requêtes (amorçage CSRF, rafraîchissement) sans se heurter à un
 * corps déjà consommé.
 */
export function stubFetch(routes: RouteStub[], fallback?: () => Response) {
  const spy = vi.fn<typeof fetch>((input) => {
    const url = String(input)
    const route = routes.find((candidate) => url.includes(candidate.match))

    if (route) return Promise.resolve(route.respond())
    if (fallback) return Promise.resolve(fallback())

    return Promise.resolve(
      jsonResponse({ code: 'not_found', message: 'Inconnu.', errors: {} }, 404),
    )
  })

  vi.stubGlobal('fetch', spy)
  return spy
}

/** Pose un cookie CSRF pour que le client n'ait pas à l'amorcer. */
export function seedCsrfCookie(value = 'jeton-de-test'): string {
  document.cookie = `${CSRF_COOKIE}=${value}`
  return value
}

export function clearCsrfCookie(): void {
  document.cookie = `${CSRF_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT`
}

/** Stub minimal renvoyant « non authentifié » sur `/auth/me/`. */
export function stubAnonymous() {
  return stubFetch([
    {
      match: '/auth/csrf/',
      respond: () => jsonResponse({ detail: 'ok' }),
    },
    {
      match: '/auth/me/',
      respond: () =>
        jsonResponse(
          { code: 'not_authenticated', message: 'Authentification requise.', errors: {} },
          401,
        ),
    },
  ])
}
