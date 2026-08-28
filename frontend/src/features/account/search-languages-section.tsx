import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Languages } from 'lucide-react'
import { toast } from 'sonner'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { settingsQueryKey, updateSettings } from '@/features/auth/api'
import { useSettings } from '@/features/settings/use-settings'
import type { UserSettings } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

/** Aligné sur la limite du backend. */
const MAX_LANGUAGES = 5

/**
 * Langues interrogées par la recherche de produits de marque (spec 11 §3).
 *
 * Open Food Facts indexe le nom des produits par langue : chercher uniquement
 * en français rend invisibles les produits nommés ailleurs. Le réglage suit le
 * compte, parce qu'on ne fait pas ses courses toujours au même endroit.
 *
 * Le catalogue vient du serveur, qui valide déjà les codes : le recopier ici
 * garantirait qu'il diverge un jour.
 */
export function SearchLanguagesSection() {
  const { data: settings, isLoading } = useSettings()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (languages: string[]) => updateSettings({ food_search_languages: languages }),
    onSuccess: (updated: UserSettings) => {
      queryClient.setQueryData(settingsQueryKey, updated)
    },
    onError: (error) => toast.error(describeError(error)),
  })

  const selected = settings?.food_search_languages ?? []
  const catalogue = settings?.available_food_search_languages ?? []

  const toggle = (code: string, checked: boolean) => {
    const next = checked ? [...selected, code] : selected.filter((item) => item !== code)
    // Le serveur refuserait une liste vide : on ne propose pas un geste qui
    // échouerait, on empêche de décocher la dernière.
    if (next.length === 0 || next.length > MAX_LANGUAGES) return
    mutation.mutate(next)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h2" className="flex items-center gap-2">
          <Languages aria-hidden="true" className="size-4" />
          Langues de recherche
          {mutation.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        </CardTitle>
        <CardDescription>
          Les produits de marque sont indexés par langue. Ajoutez celle du pays où vous faites vos
          courses pour que la recherche les trouve. {MAX_LANGUAGES} langues au maximum.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div aria-busy="true" className="bg-muted h-24 animate-pulse rounded-lg" />
        ) : (
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {catalogue.map((language) => {
              const checked = selected.includes(language.code)
              const last = checked && selected.length === 1
              const full = !checked && selected.length >= MAX_LANGUAGES

              return (
                <li key={language.code}>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="size-4"
                      checked={checked}
                      disabled={last || full || mutation.isPending}
                      onChange={(event) => toggle(language.code, event.target.checked)}
                    />
                    {language.label}
                  </label>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
