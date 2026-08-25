import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormError } from '@/components/form/form-error'
import { NumberField } from '@/components/form/number-field'
import { Button } from '@/components/ui/button'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'
import type { NutritionGoal } from '@/lib/api/types'

import { useUpdateGoal } from './use-goals'

const goalSchema = z.object({
  daily_calories: z.string().min(1, 'Les calories sont obligatoires.'),
  protein_g: z.string().min(1, 'Les protéines sont obligatoires.'),
  carbs_g: z.string().min(1, 'Les glucides sont obligatoires.'),
  fat_g: z.string().min(1, 'Les lipides sont obligatoires.'),
  fiber_g: z.string(),
})

type GoalValues = z.infer<typeof goalSchema>

const FIELDS = ['daily_calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g'] as const

function round(value: string): string {
  return String(Math.round(Number(value)))
}

/** Édition manuelle de l'objectif en cours (spec 01 §4). */
export function GoalForm({ goal }: { goal: NutritionGoal }) {
  const mutation = useUpdateGoal(goal.id)

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm<GoalValues>({
    resolver: zodResolver(goalSchema),
    defaultValues: {
      daily_calories: round(goal.daily_calories),
      protein_g: round(goal.protein_g),
      carbs_g: round(goal.carbs_g),
      fat_g: round(goal.fat_g),
      fiber_g: goal.fiber_g ? round(goal.fiber_g) : '',
    },
  })

  const { formError, setFormError, handleApiError } = useApiFormErrors<GoalValues>(setError)

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation
      .mutateAsync({
        ...values,
        fiber_g: values.fiber_g || null,
        // La saisie manuelle change l'origine des valeurs.
        calories_source: 'manual',
        macros_source: 'manual',
      })
      .then((updated) => {
        reset({
          daily_calories: round(updated.daily_calories),
          protein_g: round(updated.protein_g),
          carbs_g: round(updated.carbs_g),
          fat_g: round(updated.fat_g),
          fiber_g: updated.fiber_g ? round(updated.fiber_g) : '',
        })
        toast.success('Objectif mis à jour.')
      })
      .catch((error: unknown) => handleApiError(error, FIELDS))
  })

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
      <FormError message={formError} />

      <NumberField
        label="Calories"
        unit="kcal"
        step="1"
        registration={register('daily_calories')}
        error={errors.daily_calories}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <NumberField
          label="Protéines"
          unit="g"
          step="1"
          registration={register('protein_g')}
          error={errors.protein_g}
        />
        <NumberField
          label="Glucides"
          unit="g"
          step="1"
          registration={register('carbs_g')}
          error={errors.carbs_g}
        />
        <NumberField
          label="Lipides"
          unit="g"
          step="1"
          registration={register('fat_g')}
          error={errors.fat_g}
        />
      </div>

      <NumberField
        label="Fibres (facultatif)"
        unit="g"
        step="1"
        hint="Laisser vide si vous ne souhaitez pas suivre les fibres."
        registration={register('fiber_g')}
        error={errors.fiber_g}
      />

      <Button type="submit" className="self-start" disabled={!isDirty || mutation.isPending}>
        {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
      </Button>
    </form>
  )
}
