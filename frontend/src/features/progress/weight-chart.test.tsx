import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ChartSeries } from '@/lib/api/types'

import { ProgressChart } from './weight-chart'

function series(overrides: Partial<ChartSeries> = {}): ChartSeries {
  return {
    metric: 'weight',
    unit: 'kg',
    from: '2026-05-29',
    to: '2026-08-26',
    points: [],
    target: null,
    trend_per_week: null,
    ...overrides,
  }
}

function point(date: string, value: string, average = value) {
  return { date, value, moving_average: average }
}

/** Abscisses de la première polyligne, dans l'ordre du tracé. */
function xCoordinates(container: HTMLElement): number[] {
  const raw = container.querySelector('polyline')?.getAttribute('points') ?? ''
  return raw
    .split(' ')
    .filter(Boolean)
    .map((pair) => Number(pair.split(',')[0]))
}

describe('Courbe de progression', () => {
  it('invite à saisir quand la période est vide', () => {
    render(<ProgressChart series={series()} label="Poids" />)

    expect(screen.getByText(/Aucune mesure sur cette période/)).toBeInTheDocument()
  })

  it('affiche un point unique sans tracer de ligne', () => {
    const { container } = render(
      <ProgressChart series={series({ points: [point('2026-08-26', '80.00')] })} label="Poids" />,
    )

    expect(container.querySelectorAll('polyline')).toHaveLength(0)
    expect(container.querySelectorAll('circle')).toHaveLength(1)
    expect(screen.queryByText(/Tendance/)).not.toBeInTheDocument()
  })

  it('trace les mesures et leur moyenne mobile', () => {
    const { container } = render(
      <ProgressChart
        series={series({
          points: [
            point('2026-08-20', '80.00'),
            point('2026-08-23', '79.00', '79.50'),
            point('2026-08-26', '78.00', '79.00'),
          ],
        })}
        label="Poids"
      />,
    )

    // Une polyligne pour les mesures, une pour la moyenne mobile.
    expect(container.querySelectorAll('polyline')).toHaveLength(2)
    expect(container.querySelectorAll('circle')).toHaveLength(3)
  })

  it('place les points selon leur date et non selon leur rang', () => {
    // Deux mesures à un jour d'écart, puis une trente jours plus tard : un axe
    // ordinal les espacerait identiquement et masquerait le trou.
    const { container } = render(
      <ProgressChart
        series={series({
          points: [
            point('2026-07-26', '80.00'),
            point('2026-07-27', '79.00'),
            point('2026-08-26', '78.00'),
          ],
        })}
        label="Poids"
      />,
    )

    const [first, second, third] = xCoordinates(container)
    expect(second! - first!).toBeLessThan((third! - second!) / 10)
  })

  it('propose une alternative textuelle à la courbe', () => {
    render(
      <ProgressChart
        series={series({
          points: [point('2026-08-20', '80.00'), point('2026-08-26', '78.00', '79.00')],
        })}
        label="Poids"
      />,
    )

    const rows = within(screen.getByRole('table')).getAllByRole('row')
    // Une ligne d'en-tête et une par mesure.
    expect(rows).toHaveLength(3)
    expect(screen.getByRole('img')).toHaveAccessibleName(/Poids du .* au .*, 2 mesures/)
  })

  it('signale l’objectif et la tendance quand ils existent', () => {
    render(
      <ProgressChart
        series={series({
          points: [point('2026-08-19', '80.00'), point('2026-08-26', '79.00', '79.50')],
          target: '78.00',
          trend_per_week: '-1.00',
        })}
        label="Poids"
      />,
    )

    expect(screen.getByText('Objectif')).toBeInTheDocument()
    expect(screen.getByText(/Tendance −1 kg par semaine/)).toBeInTheDocument()
  })

  it('reste lisible quand toutes les mesures sont identiques', () => {
    const { container } = render(
      <ProgressChart
        series={series({
          points: [point('2026-08-20', '80.00'), point('2026-08-26', '80.00')],
        })}
        label="Poids"
      />,
    )

    // Sans marge sur une plage nulle, les ordonnées seraient `NaN`.
    const ys = (container.querySelector('polyline')?.getAttribute('points') ?? '')
      .split(' ')
      .filter(Boolean)
      .map((pair) => Number(pair.split(',')[1]))
    expect(ys.every((value) => Number.isFinite(value))).toBe(true)
  })
})
