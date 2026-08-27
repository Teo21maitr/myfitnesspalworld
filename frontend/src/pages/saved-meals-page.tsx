import { Copy, Loader2, Trash2, TriangleAlert, UtensilsCrossed } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import { useMealTypes } from '@/features/diary/use-diary'
import { SavedMealForm } from '@/features/saved-meals/saved-meal-form'
import {
  useAddSavedMealToDiary,
  useCreateSavedMeal,
  useDeleteSavedMeal,
  useDuplicateSavedMeal,
  useSavedMeals,
} from '@/features/saved-meals/use-saved-meals'
import type { SavedMeal } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

function SavedMealCard({ meal }: { meal: SavedMeal }) {
  const navigate = useNavigate()
  const dateId = useId()

  const mealTypes = useMealTypes()
  const add = useAddSavedMealToDiary()
  const duplicate = useDuplicateSavedMeal()
  const remove = useDeleteSavedMeal()

  const meals = useMemo(
    () => (Array.isArray(mealTypes.data) ? mealTypes.data : []).filter((type) => type.is_active),
    [mealTypes.data],
  )

  const [date, setDate] = useState(today())
  const [mealTypeId, setMealTypeId] = useState('')
  const selectedMeal = mealTypeId || (meals[0] ? String(meals[0].id) : '')

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h3" className="text-base">
          {meal.name}
        </CardTitle>
        <CardDescription>
          {meal.items.length} élément{meal.items.length > 1 ? 's' : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="flex flex-col">
          {meal.items.map((item) => (
            <li
              key={item.id}
              className="flex items-baseline justify-between gap-4 border-b py-1.5 last:border-b-0"
            >
              <span className="text-sm">
                {item.item_name}
                {item.food === null && item.recipe === null && (
                  <span className="text-muted-foreground ml-2 text-xs">source supprimée</span>
                )}
              </span>
              <span className="text-muted-foreground text-sm">
                {Number(item.quantity).toLocaleString('fr-FR')} {item.unit_label}
              </span>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap items-end gap-2">
          <SelectField
            label="Repas"
            className="w-40"
            options={meals.map((type) => ({ value: String(type.id), label: type.name }))}
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

          <Button
            type="button"
            disabled={add.isPending || selectedMeal === ''}
            onClick={() =>
              add.mutate(
                { id: meal.id, date, meal_type_id: Number(selectedMeal) },
                {
                  onSuccess: (result) => {
                    // Les éléments dont la source a disparu sont nommés plutôt
                    // qu'ignorés en silence.
                    if (result.skipped.length > 0) {
                      toast.warning(
                        `Ajouté, sauf ${result.skipped.length} élément${result.skipped.length > 1 ? 's' : ''} : ${result.skipped.join(', ')}.`,
                      )
                    } else {
                      toast.success('Ajouté au journal.')
                    }
                    void navigate(`/journal?date=${date}`)
                  },
                },
              )
            }
          >
            {add.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
            Ajouter au journal
          </Button>
        </div>

        {add.isError && (
          <p role="alert" className="text-destructive text-sm">
            {describeError(add.error)}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={duplicate.isPending}
            onClick={() =>
              duplicate.mutate(meal.id, { onSuccess: () => toast.success('Repas dupliqué.') })
            }
          >
            <Copy aria-hidden="true" className="size-4" />
            Dupliquer
          </Button>

          {meal.is_editable && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-destructive"
              aria-label={`Supprimer ${meal.name}`}
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(meal.id, { onSuccess: () => toast.success('Repas supprimé.') })
              }
            >
              <Trash2 aria-hidden="true" className="size-4" />
              Supprimer
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

/** Repas enregistrés (spec 01 §13). */
export function SavedMealsPage() {
  const { data, error, isPending } = useSavedMeals()
  const create = useCreateSavedMeal()

  const meals = Array.isArray(data?.results) ? data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mes repas</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Des ensembles réutilisables d’aliments et de recettes déjà portionnés.
        </p>
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <div className="bg-muted h-24 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement des repas…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {data && meals.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="text-base">
              <UtensilsCrossed aria-hidden="true" className="mr-2 inline size-4" />
              Aucun repas enregistré
            </CardTitle>
            <CardDescription>
              Enregistrez un ensemble que vous mangez souvent : il s’ajoutera au journal en un
              geste, sous forme d’entrées normales et modifiables une à une.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {meals.map((meal) => (
        <SavedMealCard key={meal.id} meal={meal} />
      ))}

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Nouveau repas
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SavedMealForm
            isPending={create.isPending}
            error={create.error}
            onSubmit={(payload) =>
              create.mutate(payload, { onSuccess: () => toast.success('Repas enregistré.') })
            }
          />
        </CardContent>
      </Card>
    </div>
  )
}
