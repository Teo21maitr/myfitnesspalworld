import { Loader2 } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DatePickerList } from '@/features/diary/date-picker-list'
import { useRecipes } from '@/features/recipes/use-recipes'
import { describeError } from '@/lib/query-client'

import { useGenerateShoppingList, useShoppingLists } from './use-shopping'

/**
 * Génération d'une liste depuis des recettes ou des journées (spec 01 §16).
 *
 * Le sélecteur de dates est celui de la copie de journées : c'est le même
 * geste, et deux variantes finiraient par diverger.
 */
export function GenerateForm({ onDone }: { onDone?: (id: number) => void }) {
  const nameId = useId()
  const targetId = useId()

  const [target, setTarget] = useState('')
  const [name, setName] = useState('')
  const [recipeIds, setRecipeIds] = useState<number[]>([])
  const [dates, setDates] = useState<string[]>([])

  const recipesQuery = useRecipes()
  const listsQuery = useShoppingLists()
  const generate = useGenerateShoppingList()

  const existing = useMemo(
    () =>
      (Array.isArray(listsQuery.data?.results) ? listsQuery.data.results : []).filter(
        (list) => list.is_editable,
      ),
    [listsQuery.data],
  )

  const recipes = useMemo(
    () => (Array.isArray(recipesQuery.data?.results) ? recipesQuery.data.results : []),
    [recipesQuery.data],
  )

  const isValid = recipeIds.length > 0 || dates.length > 0

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!isValid) return

    generate.mutate(
      {
        shopping_list_id: target === '' ? undefined : Number(target),
        name: target === '' ? name.trim() || undefined : undefined,
        recipe_ids: recipeIds.length > 0 ? recipeIds : undefined,
        dates: dates.length > 0 ? dates : undefined,
      },
      {
        onSuccess: (list) => {
          toast.success('Liste générée.')
          setName('')
          setRecipeIds([])
          setDates([])
          onDone?.(list.id)
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      {existing.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={targetId}>Où ajouter</Label>
          <select
            id={targetId}
            className="border-input bg-background h-11 w-full rounded-md border px-3 text-base"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          >
            <option value="">Dans une nouvelle liste</option>
            {existing.map((list) => (
              <option key={list.id} value={String(list.id)}>
                {list.name}
              </option>
            ))}
          </select>
          <p className="text-muted-foreground text-xs">
            Compléter une liste existante fusionne les quantités des mêmes ingrédients.
          </p>
        </div>
      )}

      {target === '' && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={nameId}>Nom (facultatif)</Label>
          <Input
            id={nameId}
            value={name}
            placeholder="Courses du samedi"
            onChange={(event) => setName(event.target.value)}
          />
        </div>
      )}

      {recipes.length > 0 && (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">Depuis des recettes</legend>
          {recipes.map((recipe) => (
            <label key={recipe.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={recipeIds.includes(recipe.id)}
                onChange={(event) =>
                  setRecipeIds((current) =>
                    event.target.checked
                      ? [...current, recipe.id]
                      : current.filter((id) => id !== recipe.id),
                  )
                }
              />
              {recipe.name}
            </label>
          ))}
        </fieldset>
      )}

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">Depuis des journées</span>
        <DatePickerList dates={dates} onChange={setDates} />
        <p className="text-muted-foreground text-xs">
          Une recette journalisée verse ses ingrédients, à l’échelle des portions consommées.
        </p>
      </div>

      {generate.isError && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(generate.error)}
        </p>
      )}

      <Button type="submit" className="self-start" disabled={generate.isPending || !isValid}>
        {generate.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        Générer la liste
      </Button>
    </form>
  )
}
