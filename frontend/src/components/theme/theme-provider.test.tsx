import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ThemeProvider } from './theme-provider'
import { ThemeToggle } from './theme-toggle'
import { THEME_STORAGE_KEY } from './theme-context'

function renderToggle() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.classList.remove('dark')
})

afterEach(() => {
  window.localStorage.clear()
})

describe('ThemeProvider', () => {
  it('applique le thème clair par défaut quand le système est clair', () => {
    renderToggle()

    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('ajoute la classe dark quand l’utilisateur choisit le thème sombre', async () => {
    const user = userEvent.setup()
    renderToggle()

    await user.click(screen.getByRole('button', { name: 'Thème sombre' }))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('retire la classe dark en revenant au thème clair', async () => {
    const user = userEvent.setup()
    renderToggle()

    await user.click(screen.getByRole('button', { name: 'Thème sombre' }))
    await user.click(screen.getByRole('button', { name: 'Thème clair' }))

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('restaure la préférence enregistrée au montage', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark')

    renderToggle()

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(screen.getByRole('button', { name: 'Thème sombre' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
