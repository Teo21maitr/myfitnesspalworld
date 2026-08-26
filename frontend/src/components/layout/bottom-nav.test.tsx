import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { BottomNav } from './bottom-nav'

function renderNav() {
  return render(
    <MemoryRouter>
      <BottomNav />
    </MemoryRouter>,
  )
}

describe('Barre de navigation mobile', () => {
  it('affiche quatre destinations et un bouton d’ajout (spec 06 §2)', () => {
    renderNav()

    expect(screen.getByRole('link', { name: 'Accueil' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Journal' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Objectifs' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Compte' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ajouter' })).toBeInTheDocument()
  })

  it('garde le menu d’ajout fermé par défaut', () => {
    renderNav()

    expect(screen.getByRole('button', { name: 'Ajouter' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('ouvre le menu d’ajout sur le bouton central', async () => {
    const user = userEvent.setup()
    renderNav()

    await user.click(screen.getByRole('button', { name: 'Ajouter' }))

    const menu = screen.getByRole('menu', { name: 'Ajouter' })
    expect(menu).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Ajouter un aliment' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Scanner' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Ajout rapide' })).toBeInTheDocument()
  })

  it('referme le menu quand on clique en dehors', async () => {
    const user = userEvent.setup()
    renderNav()

    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await user.click(screen.getByRole('button', { name: 'Fermer le menu d’ajout' }))

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
