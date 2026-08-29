import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

/**
 * Le tiroir mobile porte **toute** la navigation.
 *
 * La barre du bas n'a que quatre raccourcis : sans lui, une destination qui
 * n'y figure pas devient inatteignable au doigt — c'est ce qui était arrivé à
 * « Mes repas » et à la planification.
 */

function stubApp() {
  return stubFetch([...BASE_ROUTES], () => jsonResponse(paginated([])))
}

/**
 * Le tiroir, et lui seul.
 *
 * La barre latérale rend les mêmes destinations : jsdom n'applique pas les
 * points de rupture, donc les deux coexistent dans le document. Chercher sans
 * cadrer trouverait la sidebar et ne prouverait rien du tiroir.
 */
function drawer() {
  return within(screen.getByRole('navigation', { name: 'Menu de navigation' }))
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('tiroir de navigation', () => {
  it('reste fermé tant qu’on ne l’ouvre pas', async () => {
    stubApp()
    renderRoute('/partages')

    expect(await screen.findByRole('button', { name: 'Ouvrir la navigation' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Menu de navigation' })).not.toBeInTheDocument()
  })

  it('donne accès aux destinations absentes de la barre du bas', async () => {
    const user = userEvent.setup()
    stubApp()
    renderRoute('/partages')

    await user.click(await screen.findByRole('button', { name: 'Ouvrir la navigation' }))

    for (const destination of ['Mes repas', 'Planification', 'Courses', 'Partages', 'Objectifs']) {
      expect(drawer().getByRole('link', { name: destination })).toBeInTheDocument()
    }
  })

  it('groupe les destinations', async () => {
    const user = userEvent.setup()
    stubApp()
    renderRoute('/partages')

    await user.click(await screen.findByRole('button', { name: 'Ouvrir la navigation' }))

    expect(drawer().getByText('Cuisine')).toBeInTheDocument()
    expect(drawer().getByText('Suivi')).toBeInTheDocument()
  })

  it('se ferme quand on choisit une destination', async () => {
    const user = userEvent.setup()
    stubApp()
    renderRoute('/partages')

    await user.click(await screen.findByRole('button', { name: 'Ouvrir la navigation' }))
    await user.click(drawer().getByRole('link', { name: 'Mes repas' }))

    expect(screen.queryByRole('navigation', { name: 'Menu de navigation' })).not.toBeInTheDocument()
  })

  it('se ferme par le voile', async () => {
    const user = userEvent.setup()
    stubApp()
    renderRoute('/partages')

    await user.click(await screen.findByRole('button', { name: 'Ouvrir la navigation' }))
    await user.click(
      screen.getAllByRole('button', { name: 'Fermer la navigation' })[0] as HTMLElement,
    )

    expect(screen.queryByRole('navigation', { name: 'Menu de navigation' })).not.toBeInTheDocument()
  })
})
