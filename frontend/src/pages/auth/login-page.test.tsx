import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { renderRoute } from '@/test/render'

const ANONYMOUS = {
  match: '/auth/me/',
  respond: () =>
    jsonResponse(
      { code: 'not_authenticated', message: 'Authentification requise.', errors: {} },
      401,
    ),
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Connexion', () => {
  it('affiche le formulaire et ses liens', async () => {
    stubFetch([ANONYMOUS])
    renderRoute('/connexion')

    expect(await screen.findByRole('heading', { name: 'Connexion' })).toBeInTheDocument()
    expect(screen.getByLabelText('Nom d’utilisateur')).toBeInTheDocument()
    expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Mot de passe oublié ?' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Demander un compte' })).toBeInTheDocument()
  })

  it('valide les champs obligatoires avant tout appel réseau', async () => {
    const user = userEvent.setup()
    const spy = stubFetch([ANONYMOUS])
    renderRoute('/connexion')

    await user.click(await screen.findByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByText('Le nom d’utilisateur est obligatoire.')).toBeInTheDocument()
    expect(screen.getByText('Le mot de passe est obligatoire.')).toBeInTheDocument()

    const loginCalls = spy.mock.calls.filter((call) => String(call[0]).includes('/auth/login/'))
    expect(loginCalls).toHaveLength(0)
  })

  it('affiche le message d’erreur du backend sur des identifiants faux', async () => {
    const user = userEvent.setup()
    stubFetch([
      ANONYMOUS,
      {
        match: '/auth/login/',
        respond: () =>
          jsonResponse(
            {
              code: 'invalid_credentials',
              message: 'Nom d’utilisateur ou mot de passe incorrect.',
              errors: {},
            },
            401,
          ),
      },
    ])
    renderRoute('/connexion')

    await user.type(await screen.findByLabelText('Nom d’utilisateur'), 'teo')
    await user.type(screen.getByLabelText('Mot de passe'), 'mauvais')
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(
      await screen.findByText('Nom d’utilisateur ou mot de passe incorrect.'),
    ).toBeInTheDocument()
  })

  it('explique qu’un compte en attente ne peut pas encore se connecter', async () => {
    const user = userEvent.setup()
    stubFetch([
      ANONYMOUS,
      {
        match: '/auth/login/',
        respond: () =>
          jsonResponse(
            {
              code: 'account_pending',
              message: 'Votre demande d’inscription n’a pas encore été acceptée.',
              errors: {},
            },
            401,
          ),
      },
    ])
    renderRoute('/connexion')

    await user.type(await screen.findByLabelText('Nom d’utilisateur'), 'teo')
    await user.type(screen.getByLabelText('Mot de passe'), 'un-mot-de-passe-1')
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByText(/n’a pas encore été acceptée/)).toBeInTheDocument()
  })

  function stubLoginFlow(onboardingCompleted: boolean) {
    let authenticated = false
    const account = {
      id: 1,
      username: 'teo',
      first_name: 'Téo',
      last_name: 'Maitrot',
      email: null,
      status: 'ACTIVE',
      is_staff: false,
      onboarding_completed: onboardingCompleted,
    }

    return stubFetch([
      {
        match: '/auth/me/',
        respond: () =>
          authenticated
            ? jsonResponse(account)
            : jsonResponse(
                { code: 'not_authenticated', message: 'Authentification requise.', errors: {} },
                401,
              ),
      },
      {
        match: '/auth/login/',
        respond: () => {
          authenticated = true
          return jsonResponse(account)
        },
      },
      {
        match: '/profile/settings/',
        respond: () =>
          jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
      },
      {
        match: '/health/',
        respond: () =>
          jsonResponse({
            status: 'ok',
            version: '0.1.0',
            time: '',
            checks: { database: 'ok', cache: 'ok' },
          }),
      },
    ])
  }

  async function signIn(user: ReturnType<typeof userEvent.setup>) {
    await user.type(await screen.findByLabelText('Nom d’utilisateur'), 'teo')
    await user.type(screen.getByLabelText('Mot de passe'), 'un-mot-de-passe-1')
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))
  }

  it('redirige vers la zone privée après une connexion réussie', async () => {
    const user = userEvent.setup()
    stubLoginFlow(true)
    const { router } = renderRoute('/connexion')

    await signIn(user)

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/')
    })
  })

  it('redirige vers l’onboarding si celui-ci n’est pas terminé', async () => {
    const user = userEvent.setup()
    stubLoginFlow(false)
    const { router } = renderRoute('/connexion')

    await signIn(user)

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/onboarding')
    })
  })
})
