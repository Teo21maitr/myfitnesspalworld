import {
  Apple,
  BookOpen,
  Home,
  ScanBarcode,
  Target,
  UserRound,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
}

/**
 * Navigation de la zone privée.
 *
 * La structure complète (Accueil, Journal, +, Progression, Profil sur mobile ;
 * sidebar sur desktop) est décrite par la spec 06 §2 et §3 ; seules les pages
 * existantes sont listées tant que le métier n'est pas implémenté.
 */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Accueil', Icon: Home },
  { to: '/journal', label: 'Journal', Icon: BookOpen },
  { to: '/aliments', label: 'Aliments', Icon: Apple },
  { to: '/scanner', label: 'Scanner', Icon: ScanBarcode },
  { to: '/objectifs', label: 'Objectifs', Icon: Target },
  { to: '/compte', label: 'Compte', Icon: UserRound },
]
