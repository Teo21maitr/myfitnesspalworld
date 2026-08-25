import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormError } from '@/components/form/form-error'
import { NumberField } from '@/components/form/number-field'
import { SelectField } from '@/components/form/select-field'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'
import type { FoodDetail } from '@/lib/api/types'

import { useCreateFood, useUpdateFood } from './use-foods'

const optionalDecimal = z
  .string()
  .refine((value) => value === '' || !Number.isNaN(Number(value)), {
    message: 'Indiquez un nombre.',
  })
  .refine((value) => value === '' || Number(value) >= 0, {
    message: 'La valeur ne peut pas être négative.',
  })

const foodSchema = z.object({
  name: z.string().trim().min(2, 'Le nom doit contenir au moins 2 caractères.'),
  brand: z.string().trim(),
  reference_amount: z
    .string()
    .min(1, 'La quantité de référence est obligatoire.')
    .refine((value) => Number(value) > 0, { message: 'La quantité doit être positive.' }),
  reference_unit: z.enum(['g', 'ml', 'unit']),
  energy_kcal: z
    .string()
    .min(1, 'L’énergie est obligatoire.')
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) >= 0, {
      message: 'Indiquez une énergie valide.',
    }),
  protein_g: optionalDecimal,
  carbohydrates_g: optionalDecimal,
  fat_g: optionalDecimal,
  fiber_g: optionalDecimal,
})

type FoodValues = z.infer<typeof foodSchema>

const UNIT_OPTIONS = [
  { value: 'g', label: 'grammes' },
  { value: 'ml', label: 'millilitres' },
  { value: 'unit', label: 'unité' },
]

const FIELDS = ['name', 'brand', 'reference_amount', 'reference_unit', 'energy_kcal'] as const

function toDefaults(food?: FoodDetail): FoodValues {
  const round = (value: string | null | undefined) =>
    value === null || value === undefined ? '' : String(Math.round(Number(value) * 100) / 100)

  return {
    name: food?.name ?? '',
    brand: food?.brand ?? '',
    reference_amount: food ? String(Math.round(Number(food.reference_amount))) : '100',
    reference_unit: food?.reference_unit ?? 'g',
    energy_kcal: round(food?.nutrition?.energy_kcal),
    protein_g: round(food?.nutrition?.protein_g),
    carbohydrates_g: round(food?.nutrition?.carbohydrates_g),
    fat_g: round(food?.nutrition?.fat_g),
    fiber_g: round(food?.nutrition?.fiber_g),
  }
}

/**
 * Création et modification d'un aliment personnel (spec 01 §11).
 *
 * Un champ laissé vide reste inconnu : il est envoyé `null`, jamais 0
 * (spec 01 §8).
 */
export function FoodForm({ food }: { food?: FoodDetail }) {
  const navigate = useNavigate()
  const create = useCreateFood()
  const update = useUpdateFood(food?.id ?? 0)
  const mutation = food ? update : create

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FoodValues>({
    resolver: zodResolver(foodSchema),
    defaultValues: toDefaults(food),
  })

  const { formError, setFormError, handleApiError } = useApiFormErrors<FoodValues>(setError)

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)

    const optional = (value: string) => (value === '' ? null : value)

    return mutation
      .mutateAsync({
        name: values.name,
        brand: values.brand,
        reference_amount: values.reference_amount,
        reference_unit: values.reference_unit,
        nutrition: {
          energy_kcal: values.energy_kcal,
          protein_g: optional(values.protein_g),
          carbohydrates_g: optional(values.carbohydrates_g),
          fat_g: optional(values.fat_g),
          fiber_g: optional(values.fiber_g),
        },
      })
      .then((saved) => {
        toast.success(food ? 'Aliment mis à jour.' : 'Aliment créé.')
        navigate(`/aliments/${saved.id}`)
      })
      .catch((error: unknown) => handleApiError(error, FIELDS))
  })

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
      <FormError message={formError} />

      <TextField label="Nom" registration={register('name')} error={errors.name} />
      <TextField
        label="Marque (facultatif)"
        registration={register('brand')}
        error={errors.brand}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <NumberField
          label="Quantité de référence"
          step="1"
          hint="Les valeurs ci-dessous portent sur cette quantité."
          registration={register('reference_amount')}
          error={errors.reference_amount}
        />
        <SelectField
          label="Unité"
          options={UNIT_OPTIONS}
          registration={register('reference_unit')}
          error={errors.reference_unit}
        />
      </div>

      <NumberField
        label="Énergie"
        unit="kcal"
        step="1"
        registration={register('energy_kcal')}
        error={errors.energy_kcal}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <NumberField
          label="Protéines"
          unit="g"
          step="0.1"
          registration={register('protein_g')}
          error={errors.protein_g}
        />
        <NumberField
          label="Glucides"
          unit="g"
          step="0.1"
          registration={register('carbohydrates_g')}
          error={errors.carbohydrates_g}
        />
        <NumberField
          label="Lipides"
          unit="g"
          step="0.1"
          registration={register('fat_g')}
          error={errors.fat_g}
        />
        <NumberField
          label="Fibres"
          unit="g"
          step="0.1"
          registration={register('fiber_g')}
          error={errors.fiber_g}
        />
      </div>

      <p className="text-muted-foreground text-xs">
        Un champ laissé vide reste inconnu et s’affichera « — » : il n’est pas ramené à zéro.
      </p>

      <Button type="submit" className="self-start" disabled={isSubmitting || mutation.isPending}>
        {mutation.isPending ? 'Enregistrement…' : food ? 'Enregistrer' : 'Créer l’aliment'}
      </Button>
    </form>
  )
}
