import { ArrowLeft, Copy, Loader2, Pencil, Trash2, TriangleAlert } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import { useMealTypes } from '@/features/diary/use-diary'
import { NutrientValue } from '@/features/foods/nutrient-value'
import { NUTRIENT_LABELS } from '@/features/foods/nutrients'
import { NutritionTable } from '@/features/foods/nutrition-table'
import {
  useAddRecipeToDiary,
  useDeleteRecipe,
  useDuplicateRecipe,
  useRecipe,
} from '@/features/recipes/use-recipes'
import type { RecipeDetail } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

function AddToDiary({ recipe }: { recipe: RecipeDetail }) {
  const navigate = useNavigate()
  const dateId = useId()
  const servingsId = useId()

  const mealTypes = useMealTypes()
  const add = useAddRecipeToDiary(recipe.id)

  const meals = useMemo(
    () => (Array.isArray(mealTypes.data) ? mealTypes.data : []).filter((meal) => meal.is_active),
    [mealTypes.data],
  )

  const [date, setDate] = useState(today())
  const [servings, setServings] = useState('1')
  const [mealTypeId, setMealTypeId] = useState('')

  const selectedMeal = mealTypeId || (meals[0] ? String(meals[0].id) : '')
  const numericServings = Number(servings.replace(',', '.'))
  const isValid = selectedMeal !== '' && Number.isFinite(numericServings) && numericServings > 0

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!isValid) return

    add.mutate(
      { date, meal_type_id: Number(selectedMeal), servings: String(numericServings) },
      {
        onSuccess: () => {
          toast.success('Ajouté au journal.')
          void navigate(`/journal?date=${date}`)
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={servingsId}>Portions</Label>
          <Input
            id={servingsId}
            inputMode="decimal"
            value={servings}
            onChange={(event) => setServings(event.target.value)}
          />
        </div>

        <SelectField
          label="Repas"
          options={meals.map((meal) => ({ value: String(meal.id), label: meal.name }))}
          value={selectedMeal}
          onChange={(event) => setMealTypeId(event.target.value)}
        />

        <div className="flex flex-col gap-1.5">
          <Label htmlFor={dateId}>Date</Label>
          <Input
            id={dateId}
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </div>
      </div>

      {add.isError && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(add.error)}
        </p>
      )}

      <Button type="submit" className="self-start" disabled={add.isPending || !isValid}>
        {add.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        Ajouter au journal
      </Button>
    </form>
  )
}

/** Fiche d'une recette : valeurs par portion, ingrédients, préparation. */
export function RecipeDetailPage() {
  const params = useParams()
  const navigate = useNavigate()
  const id = Number(params.id)

  const { data: recipe, error, isPending } = useRecipe(id)
  // Identifiant non numérique : la requête est désactivée et ne se
  // résoudra jamais. Sans ce cas, l'écran resterait en chargement.
  const isUnknown = !Number.isFinite(id)
  const duplicate = useDuplicateRecipe()
  const remove = useDeleteRecipe()

  if (isPending && !isUnknown) {
    return (
      <div aria-busy="true" className="mx-auto w-full max-w-2xl">
        <div className="bg-muted h-40 animate-pulse rounded-xl" />
        <span className="sr-only">Chargement de la recette…</span>
      </div>
    )
  }

  if (error || isUnknown || !recipe) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error ? describeError(error) : 'Recette introuvable.'}
        </p>
      </div>
    )
  }

  const incomplete = recipe.nutrition?.incomplete_nutrients ?? []
  // Quand l'énergie elle-même est partielle, le chiffre mis en avant est
  // sous-évalué : le taire en ferait un total d'apparence exacte.
  const energyIsPartial = incomplete.includes('energy_kcal')
  const incompleteLabels = incomplete.map((key) => NUTRIENT_LABELS[key] ?? key)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/recettes">
            <ArrowLeft aria-hidden="true" />
            Recettes
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">{recipe.name}</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {Number(recipe.servings).toLocaleString('fr-FR')} portion
          {Number(recipe.servings) > 1 ? 's' : ''}
          {recipe.description && ` · ${recipe.description}`}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Pour une portion
          </CardTitle>
          <CardDescription>
            <NutrientValue value={recipe.nutrition?.energy_kcal ?? null} unit="kcal" /> par portion
            {energyIsPartial && ' — total partiel'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {incomplete.length > 0 && (
            <p className="text-muted-foreground text-xs">
              Total partiel : {incompleteLabels.join(', ')}{' '}
              {incomplete.length > 1 ? 'ne sont pas renseignés' : 'n’est pas renseigné'} par tous
              les ingrédients. Les valeurs affichées additionnent ce qui est connu, sans compter les
              inconnues pour zéro.
            </p>
          )}
          {recipe.nutrition && <NutritionTable nutrition={recipe.nutrition} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Ajouter au journal
          </CardTitle>
        </CardHeader>
        <CardContent>
          <AddToDiary recipe={recipe} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Ingrédients
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recipe.ingredients.length === 0 ? (
            <p className="text-muted-foreground text-sm">Aucun ingrédient.</p>
          ) : (
            <ul className="flex flex-col">
              {recipe.ingredients.map((ingredient) => (
                <li
                  key={ingredient.id}
                  className="flex items-baseline justify-between gap-4 border-b py-2 last:border-b-0"
                >
                  <span className="text-sm">
                    {ingredient.food_name}
                    {ingredient.food === null && (
                      <span className="text-muted-foreground ml-2 text-xs">aliment supprimé</span>
                    )}
                  </span>
                  <span className="text-muted-foreground text-sm">
                    {Number(ingredient.quantity).toLocaleString('fr-FR')} {ingredient.unit_label}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {recipe.instructions && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="text-base">
              Préparation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-line">{recipe.instructions}</p>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {recipe.is_editable && (
          <Button asChild variant="outline" size="sm">
            <Link to={`/recettes/${recipe.id}/modifier`}>
              <Pencil aria-hidden="true" className="size-4" />
              Modifier
            </Link>
          </Button>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={duplicate.isPending}
          onClick={() =>
            duplicate.mutate(recipe.id, {
              onSuccess: (copy) => {
                toast.success('Recette dupliquée.')
                void navigate(`/recettes/${copy.id}`)
              },
            })
          }
        >
          <Copy aria-hidden="true" className="size-4" />
          Dupliquer
        </Button>

        {recipe.is_editable && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-destructive"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(recipe.id, {
                onSuccess: () => {
                  // Suppression douce : les entrées déjà journalisées restent
                  // intactes (spec 01 §14).
                  toast.success('Recette supprimée. Vos entrées de journal sont conservées.')
                  void navigate('/recettes')
                },
              })
            }
          >
            <Trash2 aria-hidden="true" className="size-4" />
            Supprimer
          </Button>
        )}
      </div>
    </div>
  )
}
