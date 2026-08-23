import { createContext } from 'react'

export type Theme = 'light' | 'dark' | 'system'

export interface ThemeContextValue {
  /** Préférence choisie par l'utilisateur. */
  theme: Theme
  /** Thème réellement appliqué, une fois `system` résolu. */
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
}

export const THEME_STORAGE_KEY = 'mfp-theme'

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)
