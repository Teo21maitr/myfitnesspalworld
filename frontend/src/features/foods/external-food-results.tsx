import { Globe, Loader2, TriangleAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { ExternalFoodCandidate } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import { useBarcodeLookup, useExternalFoodSearch } from './use-foods'

/**
 * Résultats de la recherche élargie à Open Food Facts (spec 11 §5).
 *
 * Un candidat n'est qu'une piste : ses valeurs nutritionnelles ne sont
 * chargées qu'au moment où l'utilisateur le choisit, par son code-barres.
 * Quand le produit est déjà en base, sa fiche s'ouvre directement — le quota
 * de la source est partagé par tous les comptes, autant l'économiser.
 */
export function ExternalFoodResults({ query }: { query: string }) {
  const navigate = useNavigate()
  const search = useExternalFoodSearch(query)
  const lookup = useBarcodeLookup()

  const open = (candidate: ExternalFoodCandidate) => {
    if (candidate.food_id !== null) {
      navigate(`/aliments/${candidate.food_id}`)
      return
    }
    lookup.mutate(candidate.code, {
      onSuccess: (food) => navigate(`/aliments/${food.id}`),
    })
  }

  if (search.isPending) {
    return (
      <p aria-busy="true" className="text-muted-foreground flex items-center gap-2 py-3 text-sm">
        <Loader2 aria-hidden="true" className="size-4 animate-spin" />
        Recherche sur Open Food Facts…
      </p>
    )
  }

  if (search.error) {
    return (
      <p role="alert" className="text-destructive flex items-start gap-2 py-3 text-sm">
        <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        {describeError(search.error)}
      </p>
    )
  }

  const results = search.data?.results ?? []

  if (results.length === 0) {
    return (
      <p className="text-muted-foreground py-3 text-sm">
        Aucun produit trouvé sur Open Food Facts.
      </p>
    )
  }

  return (
    <>
      <ul className="flex flex-col">
        {results.map((candidate) => (
          <li key={candidate.code} className="border-b last:border-b-0">
            <button
              type="button"
              onClick={() => open(candidate)}
              disabled={lookup.isPending}
              className="hover:bg-accent -mx-2 flex w-[calc(100%+1rem)] flex-col gap-0.5 rounded-md px-2 py-3 text-left"
            >
              <span className="flex items-baseline gap-2">
                <span className="font-medium">{candidate.name}</span>
                {candidate.brand && (
                  <span className="text-muted-foreground text-sm">{candidate.brand}</span>
                )}
              </span>
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Globe aria-hidden="true" className="size-3" />
                <span>Open Food Facts</span>
                <span aria-hidden="true">·</span>
                {/* Plusieurs fiches portent le même nom et la même marque :
                    le code-barres est le seul élément qui les distingue, et
                    il figure sur l'emballage. */}
                <span className="font-mono">{candidate.code}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>

      {lookup.isError && (
        <p role="alert" className="text-destructive flex items-start gap-2 py-3 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(lookup.error)}
        </p>
      )}
    </>
  )
}

/** Bouton déclenchant la recherche élargie. Jamais automatique (spec 11 §5). */
export function ExternalSearchButton({ onClick }: { onClick: () => void }) {
  return (
    <Button type="button" variant="outline" size="sm" onClick={onClick}>
      <Globe aria-hidden="true" className="size-4" />
      Chercher sur Open Food Facts
    </Button>
  )
}
