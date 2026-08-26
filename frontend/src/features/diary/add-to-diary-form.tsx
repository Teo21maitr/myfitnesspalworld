import { Loader2 } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { FoodDetail } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import { today } from './dates'
import { useCreateEntry, useMealTypes } from './use-diary'

/**
 * Aperçu local des valeurs consommées.
 *
 * Purement d'affichage : il rend la saisie lisible pendant qu'on tape, mais
 * les valeurs enregistrées sont toujours celles que renvoie le backend
 * (spec 05 §12).
 */
function preview(value: string | null, quantity: number, reference: number): string | null {
  if (value === null || !Number.isFinite(quantity) || reference <= 0) return null
  return String((Number(value) * quantity) / reference)
}

export function AddToDiaryForm({ food }: { food: FoodDetail }) {
  const navigate = useNavigate()
  const quantityId = useId()
  const dateId = useId()
  const mealTypes = useMealTypes()
  const create = useCreateEntry()

  const units = Array.isArray(food.available_units) ? food.available_units : []
  const [quantity, setQuantity] = useState('100')
  const [unit, setUnit] = useState(units[0] ?? 'g')
  const [date, setDate] = useState(today)
  const [mealTypeId, setMealTypeId] = useState<string>('')

  // `Array.isArray` plutôt qu'un simple `??` : une réponse de forme
  // inattendue doit dégrader l'écran, pas le faire tomber.
  const meals = useMemo(
    () => (Array.isArray(mealTypes.data) ? mealTypes.data : []).filter((meal) => meal.is_active),
    [mealTypes.data],
  )
  const selectedMeal = mealTypeId || (meals[0] ? String(meals[0].id) : '')

  // L'aperçu n'a de sens que pour une unité dont on connaît le rapport à la
  // quantité de référence. Pour une portion, le backend seul le connaît.
  const isReferenceUnit = unit === food.reference_unit
  const numericQuantity = Number(quantity.replace(',', '.'))
  const reference = Number(food.reference_amount)

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedMeal) return

    create.mutate(
      {
        date,
        meal_type_id: Number(selectedMeal),
        food_id: food.id,
        quantity: String(numericQuantity),
        unit_label: unit,
      },
      {
        onSuccess: () => {
          toast.success('Ajouté au journal.')
          navigate(`/journal?date=${date}`)
        },
      },
    )
  }

  if (units.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Cet aliment n’a aucune unité utilisable. Ajoutez-lui une portion pour pouvoir le
        journaliser.
      </p>
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={quantityId}>Quantité</Label>
          <Input
            id={quantityId}
            inputMode="decimal"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </div>

        <SelectField
          label="Unité"
          options={units.map((label) => ({ value: label, label }))}
          value={unit}
          onChange={(event) => setUnit(event.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
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

      {isReferenceUnit && (
        <dl
          aria-label="Aperçu des valeurs"
          className="bg-secondary/50 grid grid-cols-4 gap-2 rounded-lg p-3 text-sm"
        >
          {(
            [
              ['Énergie', food.nutrition?.energy_kcal ?? null, 'kcal'],
              ['Protéines', food.nutrition?.protein_g ?? null, 'g'],
              ['Glucides', food.nutrition?.carbohydrates_g ?? null, 'g'],
              ['Lipides', food.nutrition?.fat_g ?? null, 'g'],
            ] as const
          ).map(([label, value, unitLabel]) => (
            <div key={label} className="flex flex-col">
              <dt className="text-muted-foreground text-xs">{label}</dt>
              <dd className="font-medium">
                <NutrientValue
                  value={preview(value, numericQuantity, reference)}
                  unit={unitLabel}
                />
              </dd>
            </div>
          ))}
        </dl>
      )}

      {create.isError && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(create.error)}
        </p>
      )}

      <Button
        type="submit"
        className="self-start"
        disabled={create.isPending || !(numericQuantity > 0) || !selectedMeal}
      >
        {create.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        Ajouter au journal
      </Button>
    </form>
  )
}
