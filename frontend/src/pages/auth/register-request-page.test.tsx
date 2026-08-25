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

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Prénom'), 'Téo')
  await user.type(screen.getByLabelText('Nom'), 'Maitrot')
  await user.type(screen.getByLabelText('Nom d’utilisateur'), 'teo')
  await user.type(screen.getByLabelText('Mot de passe'), 'un-mot-de-passe-1')
  await user.type(screen.getByLabelText('Confirmation du mot de passe'), 'un-mot-de-passe-1')
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('Demande d’inscription', () => {
  it('affiche tous les champs, l’email étant facultatif', async () => {
    stubFetch([ANONYMOUS])
    renderRoute('/demande-inscription')

    expect(await screen.findByLabelText('Prénom')).toBeInTheDocument()
    expect(screen.getByLabelText('Nom')).toBeInTheDocument()
    expect(screen.getByLabelText('Nom d’utilisateur')).toBeInTheDocument()
    expect(screen.getByLabelText('Email (facultatif)')).toBeInTheDocument()
    expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirmation du mot de passe')).toBeInTheDocument()
  })

  it('signale les champs obligatoires manquants', async () => {
    const user = userEvent.setup()
    stubFetch([ANONYMOUS])
    renderRoute('/demande-inscription')

    await user.click(await screen.findByRole('button', { name: 'Envoyer ma demande' }))

    expect(await screen.findByText('Le prénom est obligatoire.')).toBeInTheDocument()
    expect(screen.getByText('Le nom est obligatoire.')).toBeInTheDocument()
  })

  it('refuse deux mots de passe différents', async () => {
    const user = userEvent.setup()
    stubFetch([ANONYMOUS])
    renderRoute('/demande-inscription')

    await user.type(await screen.findByLabelText('Prénom'), 'Téo')
    await user.type(screen.getByLabelText('Nom'), 'Maitrot')
    await user.type(screen.getByLabelText('Nom d’utilisateur'), 'teo')
    await user.type(screen.getByLabelText('Mot de passe'), 'un-mot-de-passe-1')
    await user.type(screen.getByLabelText('Confirmation du mot de passe'), 'autre-mot-de-passe')
    await user.click(screen.getByRole('button', { name: 'Envoyer ma demande' }))

    expect(
      await screen.findByText('Les deux mots de passe ne correspondent pas.'),
    ).toBeInTheDocument()
  })

  it('refuse une adresse email mal formée', async () => {
    const user = userEvent.setup()
    stubFetch([ANONYMOUS])
    renderRoute('/demande-inscription')

    await fillValidForm(user)
    await user.type(screen.getByLabelText('Email (facultatif)'), 'pas-un-email')
    await user.click(screen.getByRole('button', { name: 'Envoyer ma demande' }))

    expect(await screen.findByText('Adresse email invalide.')).toBeInTheDocument()
  })

  it('affiche l’erreur du backend quand le username est déjà pris', async () => {
    const user = userEvent.setup()
    stubFetch([
      ANONYMOUS,
      {
        match: '/auth/register-request/',
        respond: () =>
          jsonResponse(
            {
              code: 'validation_error',
              message: 'Données invalides.',
              errors: { username: ['Ce nom d’utilisateur est déjà utilisé.'] },
            },
            400,
          ),
      },
    ])
    renderRoute('/demande-inscription')

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Envoyer ma demande' }))

    expect(await screen.findByText('Ce nom d’utilisateur est déjà utilisé.')).toBeInTheDocument()
  })

  it('redirige vers l’écran de confirmation après succès', async () => {
    const user = userEvent.setup()
    stubFetch([
      ANONYMOUS,
      {
        match: '/auth/register-request/',
        respond: () => jsonResponse({ detail: 'Votre demande a bien été envoyée.' }, 201),
      },
    ])
    const { router } = renderRoute('/demande-inscription')

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Envoyer ma demande' }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/demande-envoyee')
    })
    expect(await screen.findByText(/un administrateur doit maintenant/i)).toBeInTheDocument()
  })
})
