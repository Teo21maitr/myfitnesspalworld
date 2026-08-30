import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'

import {
  ApiError,
  api,
  apiRequest,
  NetworkError,
  resetSessionRefresh,
  resetCsrfToken,
  setUnauthorizedHandler,
} from './client'

/** Options passées à `fetch` lors du dernier appel. */
function lastCallInit(spy: ReturnType<typeof stubFetch>): RequestInit {
  const call = spy.mock.calls.at(-1)
  const init = call?.[1]
  if (!init) throw new Error('fetch n’a pas été appelé')
  return init
}

function lastCallUrl(spy: ReturnType<typeof stubFetch>): string {
  return String(spy.mock.calls.at(-1)?.[0])
}

beforeEach(() => {
  // Le cookie CSRF existe déjà après le premier chargement de page.
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
  resetCsrfToken()
  setUnauthorizedHandler(null)
  // Le client garde en mémoire qu'un renouvellement a échoué : chaque test
  // repart d'un état neuf.
  resetSessionRefresh()
})

describe('apiRequest', () => {
  it('renvoie le JSON en cas de succès', async () => {
    stubFetch([{ match: '/health/', respond: () => jsonResponse({ status: 'ok' }) }])

    await expect(apiRequest('/health/')).resolves.toEqual({ status: 'ok' })
  })

  it('envoie les cookies pour que la session HttpOnly soit transmise', async () => {
    const spy = stubFetch([{ match: '/health/', respond: () => jsonResponse({ status: 'ok' }) }])

    await api.get('/health/')

    expect(lastCallInit(spy)).toMatchObject({ credentials: 'include' })
  })

  it('construit une URL absolue avec les paramètres de requête', async () => {
    const spy = stubFetch([{ match: '/foods/search/', respond: () => jsonResponse([]) }])

    await api.get('/foods/search/', { params: { q: 'poulet', page: 2, limit: undefined } })

    const url = lastCallUrl(spy)
    expect(url).toContain('/foods/search/')
    expect(url).toContain('q=poulet')
    expect(url).toContain('page=2')
    expect(url).not.toContain('limit')
  })

  it('transforme le format d’erreur du backend en ApiError', async () => {
    stubFetch([
      {
        match: '/diary/entries/',
        respond: () =>
          jsonResponse(
            {
              code: 'validation_error',
              message: 'Données invalides.',
              errors: { quantity: ['Ce champ est obligatoire.'] },
            },
            400,
          ),
      },
    ])

    const error = (await api.post('/diary/entries/', {}).catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(400)
    expect(error.code).toBe('validation_error')
    expect(error.message).toBe('Données invalides.')
    expect(error.fieldError('quantity')).toBe('Ce champ est obligatoire.')
  })

  it('reste exploitable si le corps d’erreur n’est pas au format attendu', async () => {
    stubFetch([
      { match: '/health/', respond: () => new Response('<html>500</html>', { status: 500 }) },
    ])

    const error = (await api.get('/health/').catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('http_error')
    expect(error.message).toBe('Erreur 500.')
  })

  it('transforme une panne réseau en NetworkError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(api.get('/health/')).rejects.toBeInstanceOf(NetworkError)
  })

  it('renvoie undefined sur une réponse 204', async () => {
    stubFetch([{ match: '/diary/entries/1/', respond: () => new Response(null, { status: 204 }) }])

    await expect(api.delete('/diary/entries/1/')).resolves.toBeUndefined()
  })
})

describe('origine', () => {
  it('adresse l’API sous la même origine que l’application', async () => {
    // C'est ce qui rend les cookies de première partie, donc acceptés par
    // Safari : le navigateur ne parle qu'à un seul hôte, nginx relaie le
    // reste. Une base absolue figerait au contraire l'adresse d'une machine
    // dans le bundle.
    const spy = stubFetch([{ match: '/diary/', respond: () => jsonResponse({ ok: true }) }])

    await api.get('/diary/', { params: { date: '2026-08-30' } })

    const url = new URL(lastCallUrl(spy))
    expect(url.origin).toBe(window.location.origin)
    expect(url.pathname).toBe('/api/v1/diary/')
    expect(url.searchParams.get('date')).toBe('2026-08-30')
  })
})

describe('CSRF', () => {
  it('ajoute l’en-tête sur les méthodes non idempotentes', async () => {
    const spy = stubFetch([{ match: '/diary/entries/', respond: () => jsonResponse({ ok: true }) }])

    await api.post('/diary/entries/', { quantity: 1 })

    const headers = lastCallInit(spy).headers as Headers
    expect(headers.get('X-CSRFToken')).toBe('jeton-de-test')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('n’ajoute pas l’en-tête sur un GET', async () => {
    const spy = stubFetch([{ match: '/health/', respond: () => jsonResponse({ ok: true }) }])

    await api.get('/health/')

    const headers = lastCallInit(spy).headers as Headers
    expect(headers.get('X-CSRFToken')).toBeNull()
  })

  it('amorce le jeton avant la première écriture quand il est absent', async () => {
    clearCsrfCookie()
    const spy = stubFetch([
      {
        match: '/auth/csrf/',
        respond: () => jsonResponse({ csrf_token: 'jeton-du-corps' }),
      },
      { match: '/diary/entries/', respond: () => jsonResponse({ ok: true }) },
    ])

    await api.post('/diary/entries/', { quantity: 1 })

    const urls = spy.mock.calls.map((call) => String(call[0]))
    expect(urls[0]).toContain('/auth/csrf/')
    expect(urls[1]).toContain('/diary/entries/')
  })

  it('emploie le jeton du corps quand le cookie est illisible', async () => {
    // Le cas de la production : l'API vit sur un autre domaine, donc
    // `document.cookie` ne la voit pas. Le navigateur envoie bien le cookie —
    // le serveur le lit — mais nous ne pouvons pas le recopier dans l'en-tête.
    clearCsrfCookie()
    const spy = stubFetch([
      { match: '/auth/csrf/', respond: () => jsonResponse({ csrf_token: 'jeton-du-corps' }) },
      { match: '/diary/entries/', respond: () => jsonResponse({ ok: true }) },
    ])

    await api.post('/diary/entries/', { quantity: 1 })

    expect((lastCallInit(spy).headers as Headers).get('X-CSRFToken')).toBe('jeton-du-corps')
  })

  it('rejoue une fois avec un jeton neuf quand le sien est périmé', async () => {
    // Un cookie effacé dans un autre onglet rendrait sinon toute écriture
    // impossible jusqu'au rechargement de la page.
    clearCsrfCookie()
    let entryCalls = 0
    const spy = stubFetch([
      { match: '/auth/csrf/', respond: () => jsonResponse({ csrf_token: `jeton-${entryCalls}` }) },
      {
        match: '/diary/entries/',
        respond: () => {
          entryCalls += 1
          if (entryCalls === 1) {
            return jsonResponse(
              { code: 'csrf_failed', message: 'Échec de la vérification CSRF.', errors: {} },
              403,
            )
          }
          return jsonResponse({ ok: true })
        },
      },
    ])

    await api.post('/diary/entries/', { quantity: 1 })

    expect(entryCalls).toBe(2)
    expect((lastCallInit(spy).headers as Headers).get('X-CSRFToken')).toBe('jeton-1')
  })

  it('ne rejoue pas un vrai refus d’accès', async () => {
    let calls = 0
    const spy = stubFetch([
      {
        match: '/diary/entries/',
        respond: () => {
          calls += 1
          return jsonResponse(
            { code: 'permission_denied', message: 'Accès refusé.', errors: {} },
            403,
          )
        },
      },
    ])

    await expect(api.post('/diary/entries/', { quantity: 1 })).rejects.toThrow(ApiError)

    expect(calls).toBe(1)
    expect(spy).toHaveBeenCalledTimes(1)
  })
})

describe('rafraîchissement silencieux', () => {
  it('renouvelle la session puis rejoue la requête après une 401', async () => {
    let profileCalls = 0
    const spy = stubFetch([
      { match: '/auth/refresh/', respond: () => jsonResponse({ id: 1, username: 'teo' }) },
      {
        match: '/profile/',
        respond: () => {
          profileCalls += 1
          return profileCalls === 1
            ? jsonResponse({ code: 'not_authenticated', message: 'Expiré.', errors: {} }, 401)
            : jsonResponse({ username: 'teo' })
        },
      },
    ])

    await expect(api.get('/profile/')).resolves.toEqual({ username: 'teo' })

    const urls = spy.mock.calls.map((call) => String(call[0]))
    expect(urls.filter((url) => url.includes('/auth/refresh/'))).toHaveLength(1)
    expect(profileCalls).toBe(2)
  })

  it('abandonne et signale la perte de session si le refresh échoue', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)

    stubFetch([
      {
        match: '/auth/refresh/',
        respond: () =>
          jsonResponse({ code: 'invalid_refresh', message: 'Session expirée.', errors: {} }, 401),
      },
      {
        match: '/profile/',
        respond: () =>
          jsonResponse({ code: 'not_authenticated', message: 'Expiré.', errors: {} }, 401),
      },
    ])

    await expect(api.get('/profile/')).rejects.toBeInstanceOf(ApiError)
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('cesse de réessayer une fois le renouvellement voué à l’échec', async () => {
    const spy = stubFetch([
      {
        match: '/auth/refresh/',
        respond: () =>
          jsonResponse({ code: 'invalid_refresh', message: 'Session expirée.', errors: {} }, 401),
      },
      {
        match: '/profile/',
        respond: () =>
          jsonResponse({ code: 'not_authenticated', message: 'Expiré.', errors: {} }, 401),
      },
    ])

    await expect(api.get('/profile/')).rejects.toBeInstanceOf(ApiError)
    await expect(api.get('/profile/')).rejects.toBeInstanceOf(ApiError)

    // Une seule tentative : sans ce garde-fou, chaque page consultée hors
    // session consommerait le quota de l'API.
    const refreshCalls = spy.mock.calls.filter((call) => String(call[0]).includes('/auth/refresh/'))
    expect(refreshCalls).toHaveLength(1)
  })

  it('ne tente pas de rafraîchir une route d’authentification', async () => {
    const spy = stubFetch([
      {
        match: '/auth/login/',
        respond: () =>
          jsonResponse(
            { code: 'invalid_credentials', message: 'Identifiants incorrects.', errors: {} },
            401,
          ),
      },
    ])

    await expect(api.post('/auth/login/', {})).rejects.toBeInstanceOf(ApiError)

    const urls = spy.mock.calls.map((call) => String(call[0]))
    expect(urls.some((url) => url.includes('/auth/refresh/'))).toBe(false)
  })

  it('ne déclenche qu’un seul rafraîchissement pour plusieurs requêtes simultanées', async () => {
    const seen = new Map<string, number>()
    const spy = stubFetch([
      { match: '/auth/refresh/', respond: () => jsonResponse({ id: 1 }) },
      {
        match: '/api',
        respond: () => {
          const count = (seen.get('resource') ?? 0) + 1
          seen.set('resource', count)
          // Les deux premiers appels (un par requête) échouent en 401.
          return count <= 2
            ? jsonResponse({ code: 'not_authenticated', message: 'Expiré.', errors: {} }, 401)
            : jsonResponse({ ok: true })
        },
      },
    ])

    await Promise.all([api.get('/profile/'), api.get('/profile/settings/')])

    const refreshCalls = spy.mock.calls.filter((call) => String(call[0]).includes('/auth/refresh/'))
    expect(refreshCalls).toHaveLength(1)
  })
})
