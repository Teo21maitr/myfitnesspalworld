import { Loader2, Trash2 } from 'lucide-react'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { RecipeDetail } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import type { IngredientPayload } from './api'
import { IngredientPicker } from './ingredient-picker'

/** Ingrédient en cours de composition : de quoi l'afficher et l'envoyer. */
interface Draft extends IngredientPayload {
  food_name: string
}

function draftsFrom(recipe: RecipeDetail | undefined): Draft[] {
  if (!recipe) return []

  return recipe.ingredients
    .filter((ingredient) => ingredient.food !== null)
    .map((ingredient) => ({
      food_id: ingredient.food as number,
      food_name: ingredient.food_name,
      quantity: String(Number(ingredient.quantity)),
      unit_label: ingredient.unit_label,
    }))
}

/**
 * Composition d'une recette (spec 01 §14).
 *
 * La nutrition n'est **pas** calculée à l'écran pendant la composition : les
 * facteurs d'unité — portions, cuillères — vivent côté serveur, et les
 * reconstituer ici reviendrait à tenir une seconde source de vérité
 * nutritionnelle, que le projet s'interdit.
 */
export function RecipeForm({
  recipe,
  isPending,
  error,
  submitLabel,
  onSubmit,
}: {
  recipe?: RecipeDetail
  isPending: boolean
  error: unknown
  submitLabel: string
  onSubmit: (payload: {
    name: string
    servings: string
    description: string
    instructions: string
    ingredients: IngredientPayload[]
  }) => void
}) {
  const nameId = useId()
  const servingsId = useId()
  const descriptionId = useId()
  const instructionsId = useId()

  const [name, setName] = useState(recipe?.name ?? '')
  const [servings, setServings] = useState(recipe ? String(Number(recipe.servings)) : '2')
  const [description, setDescription] = useState(recipe?.description ?? '')
  const [instructions, setInstructions] = useState(recipe?.instructions ?? '')
  const [ingredients, setIngredients] = useState<Draft[]>(() => draftsFrom(recipe))

  const numericServings = Number(servings.replace(',', '.'))
  const isValid = name.trim() !== '' && Number.isFinite(numericServings) && numericServings > 0

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!isValid) return

    onSubmit({
      name: name.trim(),
      servings: String(numericServings),
      description: description.trim(),
      instructions: instructions.trim(),
      ingredients: ingredients.map(({ food_id, quantity, unit_label }) => ({
        food_id,
        quantity,
        unit_label,
      })),
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <Label htmlFor={nameId}>Nom</Label>
          <Input
            id={nameId}
            value={name}
            placeholder="Blanquette de veau"
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor={servingsId}>Portions</Label>
          <Input
            id={servingsId}
            inputMode="decimal"
            value={servings}
            onChange={(event) => setServings(event.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={descriptionId}>Description (facultatif)</Label>
        <Input
          id={descriptionId}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Ingrédients</h3>

        {ingredients.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Aucun ingrédient pour l’instant. Une recette sans ingrédient vaut zéro calorie.
          </p>
        ) : (
          <ul className="flex flex-col">
            {ingredients.map((ingredient, index) => (
              <li
                key={`${ingredient.food_id}-${index}`}
                className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0"
              >
                <span className="text-sm">{ingredient.food_name}</span>
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground text-sm">
                    {Number(ingredient.quantity).toLocaleString('fr-FR')} {ingredient.unit_label}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Retirer ${ingredient.food_name}`}
                    onClick={() =>
                      setIngredients((current) => current.filter((_, at) => at !== index))
                    }
                  >
                    <Trash2 aria-hidden="true" className="size-4" />
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}

        <IngredientPicker
          onAdd={({ food, quantity, unitLabel }) =>
            setIngredients((current) => [
              ...current,
              {
                food_id: food.id,
                food_name: food.name,
                quantity,
                unit_label: unitLabel,
              },
            ])
          }
        />

        <p className="text-muted-foreground text-xs">
          Les valeurs par portion sont calculées par le serveur à l’enregistrement. Un ingrédient
          dont une valeur est inconnue rend le total partiel : il s’affichera comme tel, jamais
          ramené à zéro.
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={instructionsId}>Préparation (facultatif)</Label>
        <textarea
          id={instructionsId}
          rows={5}
          className="border-input bg-background w-full rounded-md border px-3 py-2 text-base"
          value={instructions}
          onChange={(event) => setInstructions(event.target.value)}
        />
      </div>

      {error != null && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(error)}
        </p>
      )}

      <Button type="submit" className="self-start" disabled={isPending || !isValid}>
        {isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        {submitLabel}
      </Button>
    </form>
  )
}
