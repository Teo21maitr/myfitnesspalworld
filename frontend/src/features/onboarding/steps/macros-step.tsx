import { useFormContext, useWatch } from 'react-hook-form'

import { NumberField } from '@/components/form/number-field'

import type { OnboardingValues } from '../schema'

const KCAL_PER_GRAM = { protein: 4, carbs: 4, fat: 9 } as const

function percentage(grams: string, kcalPerGram: number, calories: string): string {
  const total = Number(calories)
  if (!total) return '—'
  return `${Math.round(((Number(grams) * kcalPerGram) / total) * 100)} %`
}

/** Étape 6 — répartition des macronutriments (spec 01 §2 et §4). */
export function MacrosStep() {
  const {
    control,
    register,
    formState: { errors },
  } = useFormContext<OnboardingValues>()

  const [calories, protein, carbs, fat] = useWatch({
    control,
    name: ['daily_calories', 'protein_g', 'carbs_g', 'fat_g'],
  })

  const implied = Number(protein) * 4 + Number(carbs) * 4 + Number(fat) * 9
  const gap = Math.round(implied - Number(calories))

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Répartition proposée pour {Math.round(Number(calories))} kcal. Vous pouvez ajuster chaque
        valeur.
      </p>

      <div className="flex flex-col gap-4">
        <NumberField
          label="Protéines"
          unit="g"
          step="1"
          hint={`${percentage(protein, KCAL_PER_GRAM.protein, calories)} des calories`}
          registration={register('protein_g')}
          error={errors.protein_g}
        />
        <NumberField
          label="Glucides"
          unit="g"
          step="1"
          hint={`${percentage(carbs, KCAL_PER_GRAM.carbs, calories)} des calories`}
          registration={register('carbs_g')}
          error={errors.carbs_g}
        />
        <NumberField
          label="Lipides"
          unit="g"
          step="1"
          hint={`${percentage(fat, KCAL_PER_GRAM.fat, calories)} des calories`}
          registration={register('fat_g')}
          error={errors.fat_g}
        />
      </div>

      {Math.abs(gap) > 20 && (
        <p role="status" className="text-muted-foreground text-xs">
          Ces macros représentent {Math.round(implied)} kcal, soit {gap > 0 ? '+' : ''}
          {gap} kcal par rapport à votre objectif. En cas d’écart, ce sont les calories qui font
          foi.
        </p>
      )}
    </div>
  )
}
