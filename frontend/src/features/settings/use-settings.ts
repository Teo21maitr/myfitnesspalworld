import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { fetchSettings, settingsQueryKey, updateSettings } from '@/features/auth/api'
import { useMe } from '@/features/auth/use-auth'
import { useTheme } from '@/components/theme/use-theme'
import type { ThemeMode, UserSettings } from '@/lib/api/types'

/** Préférences de l'utilisateur, chargées seulement s'il est connecté. */
export function useSettings() {
  const { data: user } = useMe()

  return useQuery({
    queryKey: settingsQueryKey,
    queryFn: fetchSettings,
    enabled: Boolean(user),
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Thème courant et sa persistance.
 *
 * `localStorage` reste la source immédiate — cela évite tout clignotement au
 * chargement — et le choix est répliqué côté serveur pour suivre l'utilisateur
 * d'un appareil à l'autre.
 */
export function useThemePreference() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const { data: user } = useMe()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (mode: ThemeMode) => updateSettings({ theme_mode: mode }),
    onSuccess: (settings: UserSettings) => {
      queryClient.setQueryData(settingsQueryKey, settings)
    },
  })

  const changeTheme = (mode: ThemeMode) => {
    setTheme(mode)
    if (user) {
      mutation.mutate(mode)
    }
  }

  return { theme, resolvedTheme, changeTheme, isSaving: mutation.isPending }
}

/**
 * Aligne le thème local sur celui enregistré côté serveur.
 *
 * Monté dans la zone privée : à la connexion, la préférence du compte prend
 * le pas sur celle du navigateur.
 */
export function ThemeSync() {
  const { data: settings } = useSettings()
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    if (settings && settings.theme_mode !== theme) {
      setTheme(settings.theme_mode)
    }
    // Volontairement limité au chargement des paramètres : un changement local
    // ultérieur ne doit pas être écrasé.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings?.theme_mode])

  return null
}
