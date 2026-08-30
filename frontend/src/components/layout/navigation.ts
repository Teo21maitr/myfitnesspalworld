import {
  Apple,
  Bell,
  BookOpen,
  CalendarDays,
  ChartNoAxesColumn,
  ChefHat,
  CircleQuestionMark,
  FileText,
  Home,
  Images,
  ScanBarcode,
  ScanEye,
  ScanText,
  Share2,
  ShoppingCart,
  Target,
  TrendingUp,
  UserRound,
  Users,
  UtensilsCrossed,
  Zap,
  type LucideIcon,
} from 'lucide-react'

/**
 * Les destinations de l'application, en **une seule liste**.
 *
 * Il y en avait deux : une pour la barre latérale, une pour mobile. Chaque
 * étape remplissait la première et rapiéçait l'accès mobile en glissant un
 * bouton dans « Mon compte ». « Mes repas » a fini inatteignable au doigt, et
 * « Ajout rapide » inatteignable à la souris — deux fois le même défaut, dans
 * les deux sens.
 *
 * Une liste unique, deux rendus : la barre latérale sur desktop, un tiroir sur
 * mobile. La parité devient structurelle plutôt que surveillée, et un test
 * échoue si une route du routeur cesse d'être atteignable (spec 06 §1).
 *
 * Le groupement n'est pas décoratif : dix-neuf destinations à plat ne se lisent
 * ni en colonne ni en tiroir.
 */

export interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
  /** Libellé de la barre du bas, quand `label` y serait trop long. */
  short?: string
}

export interface NavSection {
  title: string
  items: NavItem[]
}

export const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Au quotidien',
    items: [
      { to: '/', label: 'Accueil', Icon: Home },
      { to: '/journal', label: 'Journal', Icon: BookOpen },
      { to: '/ajout-rapide', label: 'Ajout rapide', Icon: Zap },
    ],
  },
  {
    title: 'Aliments',
    items: [
      { to: '/aliments', label: 'Rechercher', Icon: Apple },
      { to: '/mes-aliments', label: 'Mes aliments', Icon: UtensilsCrossed },
      { to: '/scanner', label: 'Scanner un code-barres', Icon: ScanBarcode },
      { to: '/scanner-repas', label: 'Scanner un repas', Icon: ScanEye },
      { to: '/scanner-etiquette', label: 'Lire une étiquette', Icon: ScanText },
    ],
  },
  {
    title: 'Cuisine',
    items: [
      { to: '/recettes', label: 'Recettes', Icon: ChefHat },
      { to: '/mes-repas', label: 'Mes repas', Icon: UtensilsCrossed },
      { to: '/planification', label: 'Planification', Icon: CalendarDays },
      { to: '/courses', label: 'Courses', Icon: ShoppingCart },
    ],
  },
  {
    title: 'Suivi',
    items: [
      { to: '/progression', label: 'Progression', Icon: TrendingUp },
      { to: '/photos', label: 'Photos', Icon: Images },
      { to: '/objectifs', label: 'Objectifs', Icon: Target },
      { to: '/analyse', label: 'Analyse', Icon: ChartNoAxesColumn },
      { to: '/rapports', label: 'Rapports', Icon: FileText },
    ],
  },
  {
    title: 'Partage',
    items: [
      { to: '/amis', label: 'Amis', Icon: Users },
      { to: '/partages', label: 'Partages', Icon: Share2 },
    ],
  },
  {
    title: 'Compte',
    items: [
      { to: '/notifications', label: 'Notifications', Icon: Bell },
      { to: '/guide', label: 'Guide', Icon: CircleQuestionMark },
      { to: '/compte', label: 'Mon compte', Icon: UserRound, short: 'Compte' },
    ],
  },
]

/** Toutes les destinations, à plat. Ce que le test de parité interroge. */
export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items)

/**
 * Raccourcis de la barre du bas (spec 06 §2).
 *
 * Quatre destinations encadrant le bouton `+`. Ce sont des **raccourcis** vers
 * les écrans du quotidien, pas la navigation : celle-ci vit dans le tiroir, qui
 * porte tout.
 */
export const BOTTOM_NAV_PATHS = ['/', '/journal', '/progression', '/compte'] as const

export const BOTTOM_NAV_ITEMS: NavItem[] = BOTTOM_NAV_PATHS.map(
  (path) => NAV_ITEMS.find((item) => item.to === path) as NavItem,
)

/**
 * Entrées du menu `+`, en attendant la saisie vocale.
 *
 * Elles ne sont pas une navigation parallèle : chacune figure aussi dans le
 * tiroir. C'est le geste d'ajouter au journal qu'on rapproche du pouce, pas un
 * second chemin à tenir à jour.
 */
export const ADD_MENU_ITEMS: NavItem[] = [
  { to: '/aliments', label: 'Ajouter un aliment', Icon: Apple },
  { to: '/scanner', label: 'Scanner', Icon: ScanBarcode },
  { to: '/scanner-repas', label: 'Scanner un repas', Icon: ScanEye },
  { to: '/scanner-etiquette', label: 'Lire une étiquette', Icon: ScanText },
  { to: '/recettes', label: 'Depuis une recette', Icon: ChefHat },
  { to: '/ajout-rapide', label: 'Ajout rapide', Icon: Zap },
]
