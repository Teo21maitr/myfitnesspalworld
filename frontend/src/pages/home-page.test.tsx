import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type * as HealthApi from '@/features/health/api'
import { ApiError } from '@/lib/api/client'
import { renderWithProviders } from '@/test/render'

import { HomePage } from './home-page'

const fetchHealth = vi.hoisted(() => vi.fn())

vi.mock('@/features/health/api', async (importOriginal) => ({
  ...(await importOriginal<typeof HealthApi>()),
  fetchHealth,
}))

afterEach(() => {
  fetchHealth.mockReset()
})

describe('HomePage', () => {
  it('affiche un état de chargement puis le statut du backend', async () => {
    fetchHealth.mockResolvedValue({
      status: 'ok',
      version: '0.1.0',
      time: '2026-08-23T10:00:00+02:00',
      checks: { database: 'ok', cache: 'ok' },
    })

    renderWithProviders(<HomePage />)

    expect(screen.getByText('Chargement du statut…')).toBeInTheDocument()

    expect(await screen.findByText('API opérationnelle')).toBeInTheDocument()
    expect(screen.getByText('v0.1.0')).toBeInTheDocument()
    expect(screen.getByTestId('health-database')).toHaveTextContent('OK')
    expect(screen.getByTestId('health-cache')).toHaveTextContent('OK')
  })

  it('signale une API dégradée', async () => {
    fetchHealth.mockResolvedValue({
      status: 'degraded',
      version: '0.1.0',
      time: '2026-08-23T10:00:00+02:00',
      checks: { database: 'error', cache: 'ok' },
    })

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('API dégradée')).toBeInTheDocument()
    expect(screen.getByTestId('health-database')).toHaveTextContent('Erreur')
  })

  it('affiche un message d’erreur lisible quand l’API échoue', async () => {
    fetchHealth.mockRejectedValue(
      new ApiError(503, { code: 'unavailable', message: 'Service indisponible.', errors: {} }),
    )

    renderWithProviders(<HomePage />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Service indisponible.')
    })
  })
})
