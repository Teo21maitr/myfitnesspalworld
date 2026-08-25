import { Search } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FoodList } from '@/features/foods/food-list'
import { MINIMUM_QUERY_LENGTH, useFoodSearch, useFoodShortcuts } from '@/features/foods/use-foods'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { cn } from '@/lib/utils'

type Shortcut = 'favorites' | 'recent' | 'frequent'

const SHORTCUTS: { id: Shortcut; label: string; empty: string }[] = [
  {
    id: 'favorites',
    label: 'Favoris',
    empty: 'Aucun favori pour le moment. L’étoile d’un aliment l’ajoute ici.',
  },
  {
    id: 'recent',
    label: 'Récents',
    empty: 'Les aliments que vous ajoutez à votre journal apparaîtront ici.',
  },
  {
    id: 'frequent',
    label: 'Fréquents',
    empty: 'Vos aliments les plus utilisés apparaîtront ici.',
  },
]

export function FoodSearchPage() {
  const inputId = useId()
  const [query, setQuery] = useState('')
  const [shortcut, setShortcut] = useState<Shortcut>('favorites')

  // La recherche ne part pas à chaque frappe (spec 11 §5).
  const debouncedQuery = useDebouncedValue(query)
  const search = useFoodSearch(debouncedQuery)
  const shortcuts = useFoodShortcuts()

  const isSearching = debouncedQuery.trim().length >= MINIMUM_QUERY_LENGTH
  const activeShortcut = SHORTCUTS.find((item) => item.id === shortcut)
  const shortcutQuery = shortcuts[shortcut]

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Aliments</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Cherchez un aliment ou consultez vos habitudes.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/mes-aliments">Mes aliments</Link>
        </Button>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={inputId}>Rechercher un aliment</Label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="text-muted-foreground pointer-events-none absolute inset-y-0 left-3 my-auto size-4"
          />
          <Input
            id={inputId}
            type="search"
            autoComplete="off"
            placeholder="Poulet, pâtes, yaourt…"
            className="pl-9"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        {query.trim().length > 0 && query.trim().length < MINIMUM_QUERY_LENGTH && (
          <p className="text-muted-foreground text-xs">
            Saisissez au moins {MINIMUM_QUERY_LENGTH} caractères.
          </p>
        )}
      </div>

      {isSearching ? (
        <section aria-label="Résultats de recherche">
          <FoodList
            foods={search.data?.results}
            isPending={search.isPending}
            error={search.error}
            emptyMessage={`Aucun aliment ne correspond à « ${debouncedQuery.trim()} ».`}
          />
        </section>
      ) : (
        <section aria-label="Vos aliments">
          <div
            role="tablist"
            aria-label="Filtres"
            className="bg-secondary mb-2 flex rounded-lg p-1"
          >
            {SHORTCUTS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={shortcut === item.id}
                onClick={() => setShortcut(item.id)}
                className={cn(
                  'flex-1 rounded-md px-3 py-1.5 text-sm font-medium',
                  shortcut === item.id ? 'bg-background shadow-xs' : 'text-muted-foreground',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          <FoodList
            foods={shortcutQuery.data?.results}
            isPending={shortcutQuery.isPending}
            error={shortcutQuery.error}
            emptyMessage={activeShortcut?.empty ?? ''}
          />
        </section>
      )}
    </div>
  )
}
