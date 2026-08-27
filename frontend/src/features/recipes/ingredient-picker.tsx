import { Loader2, Plus, Search } from 'lucide-react'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NutrientValue } from '@/features/foods/nutrient-value'
import { MINIMUM_QUERY_LENGTH, useFood, useFoodSearch } from '@/features/foods/use-foods'
import type { FoodListItem } from '@/lib/api/types'

/**
 * Choix d'un aliment, de sa quantité et de son unité.
 *
 * Réutilise la recherche d'aliments existante plutôt que d'en écrire une
 * seconde : deux recherches finiraient par classer différemment.
 */
/**
 * Quantité et unité d'un aliment déjà choisi.
 *
 * Composant à part pour que la fiche ne soit demandée qu'une fois l'aliment
 * connu : appelé depuis le parent, le hook partirait chercher `/foods/NaN/`
 * dès l'affichage du champ de recherche.
 */
function SelectedFood({
  food,
  onAdd,
  onCancel,
}: {
  food: FoodListItem
  onAdd: (ingredient: { food: FoodListItem; quantity: string; unitLabel: string }) => void
  onCancel: () => void
}) {
  const quantityId = useId()
  const [quantity, setQuantity] = useState('100')
  const [unitLabel, setUnitLabel] = useState('')

  // La fiche complète porte les unités réellement calculables (spec 01 §9) :
  // le formulaire n'en propose jamais une que le backend refuserait.
  const detail = useFood(food.id)
  const units = detail.data?.available_units ?? []
  const chosenUnit = unitLabel || units[0] || 'g'

  const submit = () => {
    if (quantity.trim() === '') return

    onAdd({
      food,
      quantity: String(Number(quantity.replace(',', '.'))),
      unitLabel: chosenUnit,
    })
    onCancel()
  }

  {
    const selected = food
    return (
      <div className="flex flex-col gap-3 rounded-lg border p-3">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-medium">{selected.name}</span>
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Changer
          </Button>
        </div>

        <div className="flex items-end gap-2">
          <div className="flex flex-1 flex-col gap-1.5">
            <Label htmlFor={quantityId}>Quantité</Label>
            <Input
              id={quantityId}
              inputMode="decimal"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
          </div>

          <div className="flex flex-1 flex-col gap-1.5">
            <Label htmlFor={`${quantityId}-unit`}>Unité</Label>
            <select
              id={`${quantityId}-unit`}
              className="border-input bg-background h-11 w-full rounded-md border px-3 text-base"
              value={chosenUnit}
              onChange={(event) => setUnitLabel(event.target.value)}
            >
              {units.map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </select>
          </div>

          <Button
            type="button"
            aria-label={`Ajouter ${selected.name}`}
            onClick={submit}
            disabled={detail.isPending}
          >
            {detail.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
            Ajouter
          </Button>
        </div>
      </div>
    )
  }
}

export function IngredientPicker({
  onAdd,
}: {
  onAdd: (ingredient: { food: FoodListItem; quantity: string; unitLabel: string }) => void
}) {
  const searchId = useId()

  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<FoodListItem | null>(null)

  const search = useFoodSearch(query)
  const results = Array.isArray(search.data?.results) ? search.data.results : []

  const choose = (food: FoodListItem) => {
    setSelected(food)
    setQuery('')
  }

  if (selected) {
    return <SelectedFood food={selected} onAdd={onAdd} onCancel={() => setSelected(null)} />
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={searchId}>Chercher un ingrédient</Label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="text-muted-foreground pointer-events-none absolute inset-y-0 left-3 my-auto size-4"
          />
          <Input
            id={searchId}
            className="pl-9"
            placeholder="poulet, riz…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      {query.trim().length >= MINIMUM_QUERY_LENGTH && (
        <>
          {search.isPending && (
            <p className="text-muted-foreground text-sm" aria-busy="true">
              Recherche…
            </p>
          )}
          {!search.isPending && results.length === 0 && (
            <p className="text-muted-foreground text-sm">Aucun aliment trouvé.</p>
          )}
          <ul className="flex flex-col">
            {results.slice(0, 8).map((food) => (
              <li key={food.id} className="border-b last:border-b-0">
                <button
                  type="button"
                  onClick={() => choose(food)}
                  className="hover:bg-accent -mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-2 text-left"
                >
                  <Plus aria-hidden="true" className="text-muted-foreground size-4 shrink-0" />
                  <span className="flex flex-1 flex-col">
                    <span className="text-sm font-medium">{food.name}</span>
                    <span className="text-muted-foreground text-xs">
                      <NutrientValue value={food.energy_kcal} unit="kcal" /> pour{' '}
                      {Math.round(Number(food.reference_amount))} {food.reference_unit}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
