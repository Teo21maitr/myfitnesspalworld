import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { renderRoute } from '@/test/render'

/** Compte prêt à utiliser l'application : onboarding terminé. */
const AUTHENTICATED_USER = {
  id: 1,
  username: 'teo',
  first_name: 'Téo',
  last_name: 'Maitrot',
  email: null,
  status: 'ACTIVE',
  is_staff: false,
  onboarding_completed: true,
}

/** Compte accepté mais qui n'a pas encore configuré ses objectifs. */
const USER_WITHOUT_ONBOARDING = { ...AUTHENTICATED_USER, onboarding_completed: false }

const SETTINGS = { language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }
const HEALTH = {
  status: 'ok',
  version: '0.1.0',
  time: '2026-08-24T10:00:00+02:00',
  checks: { database: 'ok', cache: 'ok' },
}

function stubAuthenticated() {
  return stubFetch([
    { match: '/auth/me/', respond: () => jsonResponse(AUTHENTICATED_USER) },
    { match: '/profile/settings/', respond: () => jsonResponse(SETTINGS) },
    { match: '/health/', respond: () => jsonResponse(HEALTH) },
  ])
}

function stubAnonymousRoutes() {
  return stubFetch([
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

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Protection des routes', () => {
  it('redirige un visiteur non connecté vers la connexion', async () => {
    stubAnonymousRoutes()
    const { router } = renderRoute('/compte')

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/connexion')
    })
  })

  it('n’affiche aucun contenu privé avant la résolution de la session', () => {
    stubAuthenticated()
    renderRoute('/compte')

    // Tant que /auth/me/ n'a pas répondu, seul l'écran d'attente est rendu.
    expect(screen.getByRole('status')).toHaveTextContent('Chargement de votre session…')
    expect(screen.queryByText('Mon compte')).not.toBeInTheDocument()
  })

  it('affiche la route privée une fois la session résolue', async () => {
    stubAuthenticated()
    renderRoute('/compte')

    expect(await screen.findByRole('heading', { name: 'Mon compte' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Mes informations' })).toBeInTheDocument()
  })

  it('mémorise la route demandée pour y revenir après connexion', async () => {
    stubAnonymousRoutes()
    const { router } = renderRoute('/journal')

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/connexion')
    })
    expect(router.state.location.state).toMatchObject({ from: '/journal' })
  })

  it('renvoie un utilisateur déjà connecté hors des écrans publics', async () => {
    stubAuthenticated()
    const { router } = renderRoute('/connexion')

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/')
    })
  })

  it('renvoie vers l’onboarding tant qu’il n’est pas terminé', async () => {
    stubFetch([
      { match: '/auth/me/', respond: () => jsonResponse(USER_WITHOUT_ONBOARDING) },
      { match: '/profile/goals/calculate/', respond: () => jsonResponse({}) },
    ])
    const { router } = renderRoute('/compte')

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/onboarding')
    })
  })

  it('laisse accéder à l’onboarding tant qu’il n’est pas terminé', async () => {
    stubFetch([{ match: '/auth/me/', respond: () => jsonResponse(USER_WITHOUT_ONBOARDING) }])
    renderRoute('/onboarding')

    expect(
      await screen.findByRole('heading', { name: 'Configurons vos objectifs' }),
    ).toBeInTheDocument()
  })

  it('renvoie hors de l’onboarding une fois celui-ci terminé', async () => {
    stubAuthenticated()
    const { router } = renderRoute('/onboarding')

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/')
    })
  })

  it('laisse accéder au reset de mot de passe même connecté', async () => {
    stubAuthenticated()
    renderRoute('/reinitialiser-mot-de-passe?uid=abc&token=def')

    expect(await screen.findByRole('heading', { name: 'Nouveau mot de passe' })).toBeInTheDocument()
  })
})

describe('Déconnexion', () => {
  it('ferme la session et ramène à la connexion', async () => {
    const user = userEvent.setup()
    let authenticated = true

    const spy = stubFetch([
      {
        match: '/auth/logout/',
        respond: () => {
          authenticated = false
          return new Response(null, { status: 204 })
        },
      },
      {
        match: '/auth/me/',
        respond: () =>
          authenticated
            ? jsonResponse(AUTHENTICATED_USER)
            : jsonResponse(
                { code: 'not_authenticated', message: 'Authentification requise.', errors: {} },
                401,
              ),
      },
      { match: '/profile/settings/', respond: () => jsonResponse(SETTINGS) },
      { match: '/health/', respond: () => jsonResponse(HEALTH) },
    ])

    const { router } = renderRoute('/compte')

    await user.click(await screen.findByRole('button', { name: /Se déconnecter/ }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/connexion')
    })
    expect(spy.mock.calls.some((call) => String(call[0]).includes('/auth/logout/'))).toBe(true)
  })

  it('déconnecte tous les appareils', async () => {
    const user = userEvent.setup()
    let authenticated = true

    const spy = stubFetch([
      {
        match: '/auth/logout-all/',
        respond: () => {
          authenticated = false
          return new Response(null, { status: 204 })
        },
      },
      {
        match: '/auth/me/',
        respond: () =>
          authenticated
            ? jsonResponse(AUTHENTICATED_USER)
            : jsonResponse(
                { code: 'not_authenticated', message: 'Authentification requise.', errors: {} },
                401,
              ),
      },
      { match: '/profile/settings/', respond: () => jsonResponse(SETTINGS) },
      { match: '/health/', respond: () => jsonResponse(HEALTH) },
    ])

    const { router } = renderRoute('/compte')

    await user.click(await screen.findByRole('button', { name: /Déconnecter tous les appareils/ }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/connexion')
    })
    expect(spy.mock.calls.some((call) => String(call[0]).includes('/auth/logout-all/'))).toBe(true)
  })
})

describe('Suppression de compte', () => {
  it('n’active le bouton que si la confirmation correspond exactement', async () => {
    const user = userEvent.setup()
    stubAuthenticated()
    renderRoute('/compte')

    await user.click(await screen.findByRole('button', { name: 'Supprimer mon compte' }))

    const confirmButton = screen.getByRole('button', { name: 'Supprimer définitivement' })
    expect(confirmButton).toBeDisabled()

    // La casse compte : « TEO » ne suffit pas.
    await user.type(screen.getByLabelText(/pour confirmer/), 'TEO')
    expect(confirmButton).toBeDisabled()

    await user.clear(screen.getByLabelText(/pour confirmer/))
    await user.type(screen.getByLabelText(/pour confirmer/), 'teo')
    expect(confirmButton).toBeEnabled()
  })
})
