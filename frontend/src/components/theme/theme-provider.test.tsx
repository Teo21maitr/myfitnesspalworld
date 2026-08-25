import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { stubAnonymous } from '@/test/fetch-mock'
import { renderWithProviders } from '@/test/render'

import { THEME_STORAGE_KEY } from './theme-context'
import { ThemeToggle } from './theme-toggle'

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.classList.remove('dark')
  // Utilisateur anonyme : aucun enregistrement serveur du thème.
  stubAnonymous()
})

afterEach(() => {
  window.localStorage.clear()
  vi.unstubAllGlobals()
})

describe('ThemeProvider', () => {
  it('applique le thème clair par défaut quand le système est clair', () => {
    renderWithProviders(<ThemeToggle />)

    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('ajoute la classe dark quand l’utilisateur choisit le thème sombre', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: 'Thème sombre' }))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('retire la classe dark en revenant au thème clair', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: 'Thème sombre' }))
    await user.click(screen.getByRole('button', { name: 'Thème clair' }))

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('restaure la préférence enregistrée au montage', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark')

    renderWithProviders(<ThemeToggle />)

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(screen.getByRole('button', { name: 'Thème sombre' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
