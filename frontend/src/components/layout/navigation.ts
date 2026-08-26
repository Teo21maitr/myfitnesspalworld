import {
  Apple,
  BookOpen,
  Home,
  ScanBarcode,
  Target,
  UserRound,
  Zap,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
}

/**
 * Navigation mobile (spec 06 §2).
 *
 * Quatre liens encadrant un bouton `+` central, inséré par la barre elle-même.
 * Aliments et Scanner quittent la barre pour ce menu : l'action centrale du
 * quotidien est d'ajouter au journal, pas de naviguer.
 *
 * La spec place « Progression » en quatrième position ; cette page n'existe pas
 * encore et « Objectifs » tient sa place.
 */
export const MOBILE_NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Accueil', Icon: Home },
  { to: '/journal', label: 'Journal', Icon: BookOpen },
  { to: '/objectifs', label: 'Objectifs', Icon: Target },
  { to: '/compte', label: 'Compte', Icon: UserRound },
]

/** Entrées du menu `+`, en attendant Meal Scan et la saisie vocale. */
export const ADD_MENU_ITEMS: NavItem[] = [
  { to: '/aliments', label: 'Ajouter un aliment', Icon: Apple },
  { to: '/scanner', label: 'Scanner', Icon: ScanBarcode },
  { to: '/ajout-rapide', label: 'Ajout rapide', Icon: Zap },
]

/**
 * Navigation desktop (spec 06 §3).
 *
 * La sidebar a la place d'afficher chaque destination : pas de menu `+` ici.
 */
export const SIDEBAR_NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Accueil', Icon: Home },
  { to: '/journal', label: 'Journal', Icon: BookOpen },
  { to: '/aliments', label: 'Aliments', Icon: Apple },
  { to: '/scanner', label: 'Scanner', Icon: ScanBarcode },
  { to: '/objectifs', label: 'Objectifs', Icon: Target },
  { to: '/compte', label: 'Compte', Icon: UserRound },
]
