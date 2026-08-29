import { describe, expect, it } from 'vitest'

import { routes } from '@/router'

import { ADD_MENU_ITEMS, BOTTOM_NAV_ITEMS, NAV_ITEMS, NAV_SECTIONS } from './navigation'

/**
 * La parité mobile/desktop, vérifiée plutôt que surveillée (spec 06 §1).
 *
 * Il a existé deux listes de navigation. Chaque étape remplissait celle de la
 * barre latérale et rapiéçait l'accès mobile ailleurs ; « Mes repas » a fini
 * inatteignable au doigt, « Ajout rapide » inatteignable à la souris. Le défaut
 * a survécu cinq étapes parce que rien ne le cherchait.
 *
 * Ce fichier le cherche.
 */

/** Routes qui s'ouvrent depuis un écran, jamais depuis un menu. */
const CONTEXTUAL = new Set([
  '/aliments/:id',
  '/mes-aliments/:id',
  '/recettes/nouvelle',
  '/recettes/:id',
  '/recettes/:id/modifier',
  '/planification/:id',
  '/courses/:id',
  '/amis/:userId/journal',
  '/amis/:userId/progression',
  // Le fourre-tout du routeur : il n'a pas de destination.
  '/*',
])

interface RouteLike {
  path?: string
  index?: boolean
  children?: RouteLike[]
}

/** Chemins déclarés sous la coquille privée, absolus. */
function appRoutes(): string[] {
  const shell = (routes as RouteLike[]).find(
    (route) => route.path === '/' && Array.isArray(route.children),
  )
  if (!shell?.children) throw new Error('Coquille privée introuvable dans le routeur.')

  return shell.children.map((child) => (child.index ? '/' : `/${child.path ?? ''}`))
}

const DECLARED = appRoutes()
const REACHABLE = new Set([...NAV_ITEMS, ...ADD_MENU_ITEMS].map((item) => item.to))

describe('navigation', () => {
  it('déclare bien des routes à vérifier', () => {
    // Sans cette garde, une erreur d'extraction rendrait tous les tests
    // suivants vrais par vacuité.
    expect(DECLARED.length).toBeGreaterThan(15)
  })

  it.each(DECLARED)('%s est atteignable', (route) => {
    expect(REACHABLE.has(route) || CONTEXTUAL.has(route)).toBe(true)
  })

  it('ne propose aucune destination qui n’existe pas', () => {
    const inconnues = [...NAV_ITEMS, ...ADD_MENU_ITEMS]
      .map((item) => item.to)
      .filter((to) => !DECLARED.includes(to))

    expect(inconnues).toEqual([])
  })

  it('n’attend aucune route contextuelle disparue', () => {
    // Une entrée oubliée dans cette liste masquerait la disparition d'un écran.
    const fantomes = [...CONTEXTUAL].filter((route) => !DECLARED.includes(route))

    expect(fantomes).toEqual([])
  })

  it('résout les quatre raccourcis de la barre du bas', () => {
    expect(BOTTOM_NAV_ITEMS).toHaveLength(4)
    expect(BOTTOM_NAV_ITEMS.every((item) => item !== undefined)).toBe(true)
  })

  it('ne nomme pas deux fois la même destination', () => {
    const chemins = NAV_ITEMS.map((item) => item.to)

    expect(new Set(chemins).size).toBe(chemins.length)
  })

  it('groupe les destinations, sans section vide', () => {
    expect(NAV_SECTIONS.every((section) => section.items.length > 0)).toBe(true)
  })
})
