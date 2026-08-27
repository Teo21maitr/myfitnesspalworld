import { Loader2, Plus, Trash2 } from 'lucide-react'
import { useId, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { IngredientPicker } from '@/features/recipes/ingredient-picker'
import { useRecipes } from '@/features/recipes/use-recipes'
import { describeError } from '@/lib/query-client'

import type { SavedMealItemPayload } from './api'

interface Draft extends SavedMealItemPayload {
  label: string
}

/**
 * Composition d'un repas enregistré (spec 01 §13).
 *
 * Un raccourci, pas un document : il se déplie en entrées de journal normales
 * et indépendantes, qui ne dépendront plus de lui ensuite.
 */
export function SavedMealForm({
  isPending,
  error,
  onSubmit,
}: {
  isPending: boolean
  error: unknown
  onSubmit: (payload: { name: string; items: SavedMealItemPayload[] }) => void
}) {
  const nameId = useId()
  const recipeId = useId()
  const servingsId = useId()

  const [name, setName] = useState('')
  const [items, setItems] = useState<Draft[]>([])
  const [chosenRecipe, setChosenRecipe] = useState('')
  const [recipeServings, setRecipeServings] = useState('1')

  const recipesQuery = useRecipes()
  const recipes = useMemo(
    () => (Array.isArray(recipesQuery.data?.results) ? recipesQuery.data.results : []),
    [recipesQuery.data],
  )

  const isValid = name.trim() !== '' && items.length > 0

  const addRecipe = () => {
    const recipe = recipes.find((candidate) => String(candidate.id) === chosenRecipe)
    const servings = Number(recipeServings.replace(',', '.'))
    if (!recipe || !(servings > 0)) return

    setItems((current) => [
      ...current,
      {
        item_type: 'recipe',
        recipe_id: recipe.id,
        quantity: String(servings),
        label: `${recipe.name} — ${servings.toLocaleString('fr-FR')} portion${servings > 1 ? 's' : ''}`,
      },
    ])
    setChosenRecipe('')
    setRecipeServings('1')
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!isValid) return

    onSubmit({
      name: name.trim(),
      items: items.map(({ label: _label, ...item }) => item),
    })
    setName('')
    setItems([])
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={nameId}>Nom</Label>
        <Input
          id={nameId}
          value={name}
          placeholder="Mon petit-déjeuner"
          onChange={(event) => setName(event.target.value)}
        />
      </div>

      {items.length > 0 && (
        <ul className="flex flex-col">
          {items.map((item, index) => (
            <li
              key={`${item.item_type}-${index}`}
              className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0"
            >
              <span className="text-sm">{item.label}</span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Retirer ${item.label}`}
                onClick={() => setItems((current) => current.filter((_, at) => at !== index))}
              >
                <Trash2 aria-hidden="true" className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Ajouter un aliment</h3>
        <IngredientPicker
          onAdd={({ food, quantity, unitLabel }) =>
            setItems((current) => [
              ...current,
              {
                item_type: 'food',
                food_id: food.id,
                quantity,
                unit_label: unitLabel,
                label: `${food.name} — ${Number(quantity).toLocaleString('fr-FR')} ${unitLabel}`,
              },
            ])
          }
        />
      </div>

      {recipes.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Ajouter une recette</h3>
          <div className="flex items-end gap-2">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor={recipeId}>Recette</Label>
              <select
                id={recipeId}
                className="border-input bg-background h-11 w-full rounded-md border px-3 text-base"
                value={chosenRecipe}
                onChange={(event) => setChosenRecipe(event.target.value)}
              >
                <option value="">Choisir…</option>
                {recipes.map((recipe) => (
                  <option key={recipe.id} value={String(recipe.id)}>
                    {recipe.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex w-24 flex-col gap-1.5">
              <Label htmlFor={servingsId}>Portions</Label>
              <Input
                id={servingsId}
                inputMode="decimal"
                value={recipeServings}
                onChange={(event) => setRecipeServings(event.target.value)}
              />
            </div>

            <Button
              type="button"
              variant="outline"
              aria-label="Ajouter la recette"
              onClick={addRecipe}
              disabled={!chosenRecipe}
            >
              <Plus aria-hidden="true" className="size-4" />
              Ajouter
            </Button>
          </div>
        </div>
      )}

      {error != null && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(error)}
        </p>
      )}

      <Button type="submit" className="self-start" disabled={isPending || !isValid}>
        {isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        Enregistrer le repas
      </Button>
    </form>
  )
}
