import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, apiRequest, NetworkError } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockFetch(response: Response) {
  const spy = vi.fn<typeof fetch>(() => Promise.resolve(response))
  vi.stubGlobal('fetch', spy)
  return spy
}

/** Options passées à `fetch` lors du premier appel. */
function firstCallInit(spy: ReturnType<typeof mockFetch>): RequestInit {
  const init = spy.mock.calls[0]?.[1]
  if (!init) throw new Error('fetch n’a pas été appelé')
  return init
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'mfp_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('apiRequest', () => {
  it('renvoie le JSON en cas de succès', async () => {
    mockFetch(jsonResponse({ status: 'ok' }))

    await expect(apiRequest('/health/')).resolves.toEqual({ status: 'ok' })
  })

  it('envoie les cookies pour que la session HttpOnly soit transmise', async () => {
    const spy = mockFetch(jsonResponse({ status: 'ok' }))

    await api.get('/health/')

    expect(spy).toHaveBeenCalledOnce()
    expect(firstCallInit(spy)).toMatchObject({ credentials: 'include' })
  })

  it('construit une URL absolue avec les paramètres de requête', async () => {
    const spy = mockFetch(jsonResponse([]))

    await api.get('/foods/search/', { params: { q: 'poulet', page: 2, limit: undefined } })

    const url = String(spy.mock.calls[0]?.[0])
    expect(url).toContain('/foods/search/')
    expect(url).toContain('q=poulet')
    expect(url).toContain('page=2')
    expect(url).not.toContain('limit')
  })

  it('transforme le format d’erreur du backend en ApiError', async () => {
    mockFetch(
      jsonResponse(
        {
          code: 'validation_error',
          message: 'Données invalides.',
          errors: { quantity: ['Ce champ est obligatoire.'] },
        },
        400,
      ),
    )

    const error = await api.post('/diary/entries/', {}).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.status).toBe(400)
    expect(apiError.code).toBe('validation_error')
    expect(apiError.message).toBe('Données invalides.')
    expect(apiError.fieldError('quantity')).toBe('Ce champ est obligatoire.')
  })

  it('signale une réponse 401 comme non authentifiée', async () => {
    mockFetch(
      jsonResponse(
        { code: 'not_authenticated', message: 'Authentification requise.', errors: {} },
        401,
      ),
    )

    const error = (await api.get('/profile/').catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.isUnauthorized).toBe(true)
  })

  it('reste exploitable si le corps d’erreur n’est pas au format attendu', async () => {
    mockFetch(new Response('<html>500</html>', { status: 500 }))

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
    mockFetch(new Response(null, { status: 204 }))

    await expect(api.delete('/diary/entries/1/')).resolves.toBeUndefined()
  })

  it('ajoute l’en-tête CSRF sur les méthodes non idempotentes', async () => {
    document.cookie = 'mfp_csrftoken=jeton-de-test'
    const spy = mockFetch(jsonResponse({ ok: true }))

    await api.post('/diary/entries/', { quantity: 1 })

    const headers = firstCallInit(spy).headers as Headers
    expect(headers.get('X-CSRFToken')).toBe('jeton-de-test')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('n’ajoute pas l’en-tête CSRF sur un GET', async () => {
    document.cookie = 'mfp_csrftoken=jeton-de-test'
    const spy = mockFetch(jsonResponse({ ok: true }))

    await api.get('/health/')

    const headers = firstCallInit(spy).headers as Headers
    expect(headers.get('X-CSRFToken')).toBeNull()
  })
})
