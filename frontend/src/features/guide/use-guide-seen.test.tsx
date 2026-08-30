import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { markGuideSeen, useGuideUnseen } from './use-guide-seen'

function Sonde() {
  return <p>{useGuideUnseen() ? 'guide non lu' : 'guide lu'}</p>
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('mémoire du guide', () => {
  it('signale le guide comme non lu au premier passage', () => {
    render(<Sonde />)

    expect(screen.getByText('guide non lu')).toBeInTheDocument()
  })

  it('ne le signale plus une fois ouvert', () => {
    markGuideSeen()
    render(<Sonde />)

    expect(screen.getByText('guide lu')).toBeInTheDocument()
  })

  it('se met à jour sans rechargement quand le guide s’ouvre', () => {
    render(<Sonde />)
    expect(screen.getByText('guide non lu')).toBeInTheDocument()

    // `act` : la notification part hors du cycle de React, qui doit rendre
    // avant l'assertion.
    act(() => markGuideSeen())

    expect(screen.getByText('guide lu')).toBeInTheDocument()
  })

  it('ne casse pas quand le navigateur refuse le stockage', () => {
    // Navigation privée, ou stockage désactivé : `localStorage` lève au lieu
    // de rendre `null`. L'invitation reste affichée, ce qui est sans
    // conséquence — contrairement à une page blanche.
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new DOMException('refusé')
      },
    })

    try {
      expect(() => render(<Sonde />)).not.toThrow()
      expect(screen.getByText('guide non lu')).toBeInTheDocument()
      expect(() => markGuideSeen()).not.toThrow()
    } finally {
      if (original) Object.defineProperty(window, 'localStorage', original)
    }
  })
})
