import { useContext } from 'react'

import { ThemeContext, type ThemeContextValue } from './theme-context'

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme doit être utilisé à l’intérieur d’un ThemeProvider.')
  }
  return context
}
