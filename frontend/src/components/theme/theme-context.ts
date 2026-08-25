import { createContext } from 'react'

import type { ThemeMode } from '@/lib/api/types'

/** Le thème partage le vocabulaire de l'API (`UserSettings.theme_mode`). */
export type Theme = ThemeMode

export interface ThemeContextValue {
  /** Préférence choisie par l'utilisateur. */
  theme: Theme
  /** Thème réellement appliqué, une fois `system` résolu. */
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
}

export const THEME_STORAGE_KEY = 'mfp-theme'

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)
