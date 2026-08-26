import { ArrowLeft, Loader2 } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import { useCreateEntry, useMealTypes } from '@/features/diary/use-diary'
import { describeError } from '@/lib/query-client'

/** Un champ vide reste inconnu : il part `null`, jamais 0 (spec 01 §8). */
function optional(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : String(Number(trimmed.replace(',', '.')))
}

/**
 * Ajout rapide (spec 01 §12).
 *
 * Des calories suffisent ; les macros et la note sont facultatives. C'est la
 * porte de sortie quand on mange sans pouvoir détailler.
 */
export function QuickAddPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const date = searchParams.get('date') ?? today()

  const nameId = useId()
  const caloriesId = useId()
  const noteId = useId()

  const mealTypes = useMealTypes()
  const create = useCreateEntry()

  const [name, setName] = useState('')
  const [calories, setCalories] = useState('')
  const [protein, setProtein] = useState('')
  const [carbs, setCarbs] = useState('')
  const [fat, setFat] = useState('')
  const [note, setNote] = useState('')
  const [mealTypeId, setMealTypeId] = useState('')

  // `Array.isArray` plutôt qu'un simple `??` : une réponse de forme
  // inattendue doit dégrader l'écran, pas le faire tomber.
  const meals = useMemo(
    () => (Array.isArray(mealTypes.data) ? mealTypes.data : []).filter((meal) => meal.is_active),
    [mealTypes.data],
  )
  const selectedMeal = mealTypeId || (meals[0] ? String(meals[0].id) : '')
  const numericCalories = Number(calories.replace(',', '.'))

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedMeal || !(numericCalories >= 0) || calories.trim() === '') return

    create.mutate(
      {
        date,
        meal_type_id: Number(selectedMeal),
        entry_type: 'quick_add',
        name: name.trim() || undefined,
        energy_kcal: String(numericCalories),
        protein_g: optional(protein),
        carbohydrates_g: optional(carbs),
        fat_g: optional(fat),
        note: note.trim(),
      },
      {
        onSuccess: () => {
          toast.success('Ajouté au journal.')
          navigate(`/journal?date=${date}`)
        },
      },
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to={`/journal?date=${date}`}>
            <ArrowLeft aria-hidden="true" />
            Journal
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Ajout rapide</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Ce que vous avez mangé</CardTitle>
          <CardDescription>
            Les calories suffisent. Les macronutriments sont facultatifs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={nameId}>Intitulé (facultatif)</Label>
              <Input
                id={nameId}
                placeholder="Déjeuner au restaurant"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={caloriesId}>Calories</Label>
                <Input
                  id={caloriesId}
                  inputMode="decimal"
                  value={calories}
                  onChange={(event) => setCalories(event.target.value)}
                />
              </div>

              <SelectField
                label="Repas"
                options={meals.map((meal) => ({ value: String(meal.id), label: meal.name }))}
                value={selectedMeal}
                onChange={(event) => setMealTypeId(event.target.value)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {(
                [
                  ['Protéines', protein, setProtein],
                  ['Glucides', carbs, setCarbs],
                  ['Lipides', fat, setFat],
                ] as const
              ).map(([label, value, setter]) => (
                <div key={label} className="flex flex-col gap-1.5">
                  <Label htmlFor={`${caloriesId}-${label}`}>{label} (g)</Label>
                  <Input
                    id={`${caloriesId}-${label}`}
                    inputMode="decimal"
                    value={value}
                    onChange={(event) => setter(event.target.value)}
                  />
                </div>
              ))}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={noteId}>Note (facultatif)</Label>
              <Input id={noteId} value={note} onChange={(event) => setNote(event.target.value)} />
            </div>

            <p className="text-muted-foreground text-xs">
              Un champ laissé vide reste inconnu et s’affichera « — » : il n’est pas ramené à zéro.
            </p>

            {create.isError && (
              <p role="alert" className="text-destructive text-sm">
                {describeError(create.error)}
              </p>
            )}

            <Button
              type="submit"
              className="self-start"
              disabled={create.isPending || calories.trim() === '' || !selectedMeal}
            >
              {create.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
              Ajouter au journal
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
