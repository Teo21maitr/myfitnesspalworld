import { describe, expect, it } from 'vitest'

import type { MealScanCandidate, MealScanSuggestion } from '@/lib/api/types'

import {
  estimatedEnergy,
  initialLines,
  loggableLines,
  usableUnit,
  withCandidate,
  type ScanLine,
} from './lines'

function candidate(overrides: Partial<MealScanCandidate> = {}): MealScanCandidate {
  return {
    id: 7,
    name: 'Poulet, cuisse, crue',
    brand: '',
    source: 'ciqual',
    source_label: 'Ciqual',
    reference_amount: '100.000',
    reference_unit: 'g',
    nutrition: {
      energy_kcal: '120.000',
      protein_g: '20.000',
      carbohydrates_g: null,
      fat_g: '4.000',
    },
    available_units: ['g', 'kg'],
    ...overrides,
  }
}

function suggestion(overrides: Partial<MealScanSuggestion> = {}): MealScanSuggestion {
  return {
    label: 'poulet',
    estimated_quantity: '150.000',
    unit: 'g',
    confidence: 0.82,
    alternatives: [],
    candidates: [candidate()],
    ...overrides,
  }
}

function line(overrides: Partial<ScanLine> = {}): ScanLine {
  return { key: '0-poulet', foodId: 7, quantity: '150.000', unit: 'g', ...overrides }
}

describe('lignes de correction', () => {
  it('retient le premier candidat et la quantité estimée', () => {
    const [first] = initialLines([suggestion()])

    expect(first?.foodId).toBe(7)
    expect(first?.quantity).toBe('150')
    expect(first?.unit).toBe('g')
  })

  it('affiche une quantité décimale sans zéros inutiles', () => {
    const [half] = initialLines([suggestion({ estimated_quantity: '0.500' })])

    expect(half?.quantity).toBe('0.5')
  })

  it('laisse la ligne sans aliment quand rien ne correspond', () => {
    const [first] = initialLines([suggestion({ candidates: [] })])

    expect(first?.foodId).toBeNull()
    // Sans candidat, l'unité du modèle est conservée telle quelle.
    expect(first?.unit).toBe('g')
  })

  it('remplace une unité que l’aliment ne sait pas convertir', () => {
    // Des grammes sur un aliment mesuré en millilitres : le backend les
    // refuserait en 400 (spec 01 §9).
    const liquid = candidate({ reference_unit: 'ml', available_units: ['ml', 'cl'] })

    expect(usableUnit(liquid, 'g')).toBe('ml')
    expect(usableUnit(liquid, 'cl')).toBe('cl')
  })

  it('réajuste l’unité en changeant d’aliment', () => {
    const liquid = candidate({ id: 9, reference_unit: 'ml', available_units: ['ml'] })
    const both = suggestion({ candidates: [candidate(), liquid] })

    const changed = withCandidate(line(), both, 9)

    expect(changed.foodId).toBe(9)
    expect(changed.unit).toBe('ml')
  })

  it('conserve une unité toujours valable en changeant d’aliment', () => {
    const other = candidate({ id: 9, available_units: ['g', 'kg'] })
    const both = suggestion({ candidates: [candidate(), other] })

    expect(withCandidate(line({ unit: 'kg' }), both, 9).unit).toBe('kg')
  })
})

describe('énergie estimée', () => {
  it('calcule à partir de la fiche de l’aliment', () => {
    expect(estimatedEnergy(candidate(), line())).toBeCloseTo(180)
  })

  it('ne calcule rien quand le facteur est inconnu', () => {
    // Une portion : seul le serveur connaît son équivalent.
    const withPortion = candidate({ available_units: ['g', 'tranche'] })

    expect(estimatedEnergy(withPortion, line({ unit: 'tranche' }))).toBeNull()
  })

  it('ne remplace pas une énergie inconnue par zéro', () => {
    const unknown = candidate({
      nutrition: { energy_kcal: null, protein_g: null, carbohydrates_g: null, fat_g: null },
    })

    expect(estimatedEnergy(unknown, line())).toBeNull()
  })

  it('ne calcule rien sur une quantité illisible', () => {
    expect(estimatedEnergy(candidate(), line({ quantity: 'beaucoup' }))).toBeNull()
  })
})

describe('lignes journalisables', () => {
  it('écarte celles sans aliment et celles à quantité nulle', () => {
    const lines = [line(), line({ key: '1', foodId: null }), line({ key: '2', quantity: '0' })]

    expect(loggableLines(lines)).toHaveLength(1)
  })
})
