import { describe, expect, it } from 'vitest'

import type { MealType } from '@/lib/api/types'

import { activeMeals, defaultMealTypeId } from './meals'

function meal(id: number, system_key: string | null, overrides: Partial<MealType> = {}): MealType {
  return {
    id,
    name: system_key ?? 'Autre',
    slug: String(system_key ?? id),
    sort_order: id,
    is_active: true,
    is_system: system_key !== null,
    system_key,
    ...overrides,
  }
}

const MEALS = [meal(1, 'breakfast'), meal(2, 'lunch'), meal(3, 'dinner'), meal(4, 'snacks')]

function at(hour: number): Date {
  return new Date(2026, 7, 28, hour, 30)
}

describe('repas proposé par défaut', () => {
  it.each([
    [8, '1'],
    [12, '2'],
    [20, '3'],
    [16, '4'],
    [2, '4'],
  ])('à %sh propose le repas %s', (hour, attendu) => {
    expect(defaultMealTypeId(MEALS, at(hour))).toBe(attendu)
  })

  it('suit la clé système, pas le nom', () => {
    // Un repas renommé reste le dîner.
    const renommes = [meal(1, 'breakfast'), meal(3, 'dinner', { name: 'Souper' })]

    expect(defaultMealTypeId(renommes, at(20))).toBe('3')
  })

  it('retombe sur le premier repas actif quand celui de l’heure est désactivé', () => {
    const sansDiner = [meal(1, 'breakfast'), meal(2, 'lunch')]

    expect(defaultMealTypeId(sansDiner, at(20))).toBe('1')
  })

  it('ignore les repas désactivés', () => {
    const desactive = [meal(3, 'dinner', { is_active: false }), meal(4, 'snacks')]

    expect(defaultMealTypeId(desactive, at(20))).toBe('4')
  })

  it('renvoie une chaîne vide sans aucun repas', () => {
    expect(defaultMealTypeId([], at(12))).toBe('')
  })

  it('accepte un repas personnalisé sans clé système', () => {
    const personnalise = [meal(9, null)]

    expect(defaultMealTypeId(personnalise, at(12))).toBe('9')
  })
})

describe('repas actifs', () => {
  it('écarte les désactivés', () => {
    expect(
      activeMeals([meal(1, 'breakfast', { is_active: false }), meal(2, 'lunch')]),
    ).toHaveLength(1)
  })

  it('supporte une réponse de forme inattendue', () => {
    expect(activeMeals(undefined)).toEqual([])
  })
})
