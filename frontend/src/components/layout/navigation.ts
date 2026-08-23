import { BookOpen, Home, type LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
}

/**
 * Navigation du socle.
 *
 * La structure complète (Accueil, Journal, +, Progression, Profil sur mobile ;
 * sidebar sur desktop) est décrite par la spec 06 §2 et §3 ; seules les pages
 * existantes sont listées tant que le métier n'est pas implémenté.
 */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Accueil', Icon: Home },
  { to: '/journal', label: 'Journal', Icon: BookOpen },
]
