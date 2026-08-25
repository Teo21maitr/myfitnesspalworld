import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { renderRoute } from '@/test/render'

const NEUTRAL_MESSAGE =
  'Si un compte correspond à ce nom d’utilisateur et qu’une adresse email y est associée, ' +
  'un lien de réinitialisation vient d’être envoyé. Sinon, contactez l’administrateur.'

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

describe('Mot de passe oublié', () => {
  it('demande le nom d’utilisateur', async () => {
    stubFetch([ANONYMOUS])
    renderRoute('/mot-de-passe-oublie')

    expect(await screen.findByLabelText('Nom d’utilisateur')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Envoyer le lien' })).toBeInTheDocument()
  })

  it('valide que le champ est rempli', async () => {
    const user = userEvent.setup()
    stubFetch([ANONYMOUS])
    renderRoute('/mot-de-passe-oublie')

    await user.click(await screen.findByRole('button', { name: 'Envoyer le lien' }))

    expect(await screen.findByText('Le nom d’utilisateur est obligatoire.')).toBeInTheDocument()
  })

  it('affiche le message neutre du backend après envoi', async () => {
    const user = userEvent.setup()
    stubFetch([
      ANONYMOUS,
      {
        match: '/auth/forgot-password/',
        respond: () => jsonResponse({ detail: NEUTRAL_MESSAGE }),
      },
    ])
    renderRoute('/mot-de-passe-oublie')

    await user.type(await screen.findByLabelText('Nom d’utilisateur'), 'teo')
    await user.click(screen.getByRole('button', { name: 'Envoyer le lien' }))

    // Le message ne doit rien révéler sur l'existence du compte (spec 05 §12).
    expect(await screen.findByText(NEUTRAL_MESSAGE)).toBeInTheDocument()
  })
})
