import {
  Apple,
  BookOpen,
  ChefHat,
  Home,
  ScanBarcode,
  ScanEye,
  Share2,
  ShoppingCart,
  Target,
  TrendingUp,
  Users,
  UtensilsCrossed,
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
 * « Objectifs » cède la quatrième place à « Progression », que la spec y
 * place. Cette page n'ayant plus d'entrée dans la barre, elle reste atteignable
 * depuis la carte Calories de l'accueil et depuis « Mon compte » : sans cela,
 * elle deviendrait inaccessible sur mobile.
 */
export const MOBILE_NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Accueil', Icon: Home },
  { to: '/journal', label: 'Journal', Icon: BookOpen },
  { to: '/progression', label: 'Progression', Icon: TrendingUp },
  { to: '/compte', label: 'Compte', Icon: UserRound },
]

/**
 * Entrées du menu `+`, en attendant la saisie vocale.
 *
 * Les recettes y figurent : journaliser un plat qu'on a cuisiné est un geste
 * quotidien, au même titre que scanner un produit.
 */
export const ADD_MENU_ITEMS: NavItem[] = [
  { to: '/aliments', label: 'Ajouter un aliment', Icon: Apple },
  { to: '/scanner', label: 'Scanner', Icon: ScanBarcode },
  { to: '/meal-scan', label: 'Meal Scan', Icon: ScanEye },
  { to: '/recettes', label: 'Depuis une recette', Icon: ChefHat },
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
  // Le menu `+` n'existe pas sur desktop : sans cette entrée, Meal Scan y
  // serait inatteignable.
  { to: '/meal-scan', label: 'Meal Scan', Icon: ScanEye },
  { to: '/recettes', label: 'Recettes', Icon: ChefHat },
  { to: '/mes-repas', label: 'Mes repas', Icon: UtensilsCrossed },
  { to: '/courses', label: 'Courses', Icon: ShoppingCart },
  { to: '/progression', label: 'Progression', Icon: TrendingUp },
  { to: '/amis', label: 'Amis', Icon: Users },
  { to: '/partages', label: 'Partages', Icon: Share2 },
  { to: '/objectifs', label: 'Objectifs', Icon: Target },
  { to: '/compte', label: 'Compte', Icon: UserRound },
]
