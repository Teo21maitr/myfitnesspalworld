import { describe, expect, it } from 'vitest'

import { ApiError, NetworkError } from './api/client'
import { describeError } from './query-client'

describe('describeError', () => {
  it('reprend le message du backend pour une ApiError', () => {
    const error = new ApiError(400, {
      code: 'validation_error',
      message: 'Données invalides.',
      errors: {},
    })

    expect(describeError(error)).toBe('Données invalides.')
  })

  it('explique une panne réseau', () => {
    expect(describeError(new NetworkError())).toContain('Impossible de joindre le serveur')
  })

  it('reste compréhensible pour une erreur inconnue', () => {
    expect(describeError(new Error('boom'))).toBe('Une erreur inattendue est survenue.')
  })
})
