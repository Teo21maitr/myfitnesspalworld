import { describe, expect, it } from 'vitest'

import { describeUnreadable } from './nutrients'

describe('ce que la photo n’a pas donné', () => {
  it('nomme un nutriment seul', () => {
    expect(describeUnreadable(['fiber_g'])).toBe('fibres')
  })

  it('énumère deux nutriments', () => {
    expect(describeUnreadable(['fiber_g', 'sodium_mg'])).toBe('fibres et sodium')
  })

  it('énumère une liste plus longue', () => {
    expect(describeUnreadable(['fiber_g', 'sugars_g', 'sodium_mg'])).toBe(
      'fibres, sucres et sodium',
    )
  })

  it('ne dit rien quand tout a été lu', () => {
    expect(describeUnreadable([])).toBe('')
  })
})
