import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { ADD_MENU_ITEMS, NAV_ITEMS, NAV_SECTIONS } from '@/components/layout/navigation'
import { GUIDE_DESCRIPTIONS, GUIDE_STEPS } from '@/features/guide/guide-content'

import { GuidePage } from './guide-page'

function renderGuide() {
  return render(
    <MemoryRouter>
      <GuidePage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('contenu du guide', () => {
  /**
   * La garde qui compte.
   *
   * Sans elle, la prochaine fonctionnalité rejoindrait le menu et sortirait du
   * guide **muette** : le lecteur verrait un nom, une icône, et rien dessous.
   * C'est le même défaut que la parité mobile/desktop attrapait déjà, appliqué
   * à l'explication plutôt qu'à l'accès.
   */
  it('décrit chaque destination du menu', () => {
    const sansDescription = [...NAV_ITEMS, ...ADD_MENU_ITEMS]
      .filter((item) => !GUIDE_DESCRIPTIONS[item.to]?.trim())
      .map((item) => `${item.label} (${item.to})`)

    expect(sansDescription).toEqual([])
  })

  it('ne décrit rien qui n’existe pas', () => {
    const connues = new Set([...NAV_ITEMS, ...ADD_MENU_ITEMS].map((item) => item.to))
    const orphelines = Object.keys(GUIDE_DESCRIPTIONS).filter((to) => !connues.has(to))

    expect(orphelines).toEqual([])
  })

  it('ouvre sur les gestes du quotidien avant la liste', () => {
    renderGuide()

    for (const step of GUIDE_STEPS) {
      expect(screen.getByRole('link', { name: step.title })).toHaveAttribute('href', step.to)
    }
  })

  it('rend chaque section du menu, avec ses écrans et leurs liens', () => {
    renderGuide()

    for (const section of NAV_SECTIONS) {
      expect(screen.getByRole('heading', { name: section.title })).toBeInTheDocument()
    }
    for (const item of NAV_ITEMS) {
      const lien = screen.getByRole('link', { name: item.label })
      expect(lien).toHaveAttribute('href', item.to)

      const description = GUIDE_DESCRIPTIONS[item.to]
      expect(description, `${item.label} n’a pas de description`).toBeTruthy()
      expect(screen.getByText(description as string)).toBeInTheDocument()
    }
  })

  it('rappelle que les données sont privées par défaut', () => {
    renderGuide()

    expect(screen.getByText(/privées par défaut/i)).toBeInTheDocument()
  })
})
