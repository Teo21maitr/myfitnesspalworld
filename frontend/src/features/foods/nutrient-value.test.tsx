import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { NutrientValue } from './nutrient-value'

describe('NutrientValue', () => {
  it('affiche une valeur connue avec son unité', () => {
    render(<NutrientValue value="45.9" unit="kcal" />)

    expect(screen.getByText('45,9')).toBeInTheDocument()
    expect(screen.getByText('kcal')).toBeInTheDocument()
  })

  it('arrondit au dixième', () => {
    render(<NutrientValue value="12.3456" unit="g" />)

    expect(screen.getByText('12,3')).toBeInTheDocument()
  })

  it('affiche un tiret pour une valeur inconnue', () => {
    render(<NutrientValue value={null} unit="mg" />)

    // Une valeur inconnue n'est jamais affichée 0 (spec 01 §8).
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('distingue un zéro mesuré d’une valeur inconnue', () => {
    render(<NutrientValue value="0" unit="g" />)

    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })
})
