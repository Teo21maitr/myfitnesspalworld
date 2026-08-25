import { Info, RefreshCw, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useFormContext } from 'react-hook-form'

import { NumberField } from '@/components/form/number-field'
import { Button } from '@/components/ui/button'
import { describeError } from '@/lib/query-client'

import type { OnboardingValues } from '../schema'
import { useCalorieEstimate } from '../use-calorie-estimate'

/** Étape 5 — calcul des calories (spec 01 §3). */
export function CaloriesStep() {
  const {
    register,
    setValue,
    formState: { errors },
  } = useFormContext<OnboardingValues>()

  const { data: estimate, error, isPending } = useCalorieEstimate()
  const [manual, setManual] = useState(false)

  // Tant que l'utilisateur n'a pas repris la main, l'objectif suit le calcul.
  useEffect(() => {
    if (estimate && !manual) {
      setValue('daily_calories', String(Math.round(Number(estimate.daily_calories))), {
        shouldValidate: true,
      })
      setValue('protein_g', String(Math.round(Number(estimate.protein_g))))
      setValue('carbs_g', String(Math.round(Number(estimate.carbs_g))))
      setValue('fat_g', String(Math.round(Number(estimate.fat_g))))
    }
  }, [estimate, manual, setValue])

  if (isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-3">
        <div className="bg-muted h-8 w-48 animate-pulse rounded" />
        <div className="bg-muted h-4 w-64 animate-pulse rounded" />
        <span className="sr-only">Calcul de votre objectif…</span>
      </div>
    )
  }

  if (error) {
    return (
      <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
        <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        {describeError(error)}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {estimate && (
        <>
          <div className="bg-secondary flex flex-col gap-1 rounded-lg p-4">
            <span className="text-muted-foreground text-sm">Objectif quotidien estimé</span>
            <span className="text-3xl font-semibold tabular-nums">
              {Math.round(Number(estimate.daily_calories))} kcal
            </span>
            <span className="text-muted-foreground text-xs">
              Métabolisme de base {Math.round(Number(estimate.bmr))} kcal · dépense estimée{' '}
              {Math.round(Number(estimate.tdee))} kcal
            </span>
          </div>

          {estimate.warnings.map((warning) => (
            <p
              key={warning}
              role="alert"
              className="text-warning-foreground bg-warning/20 flex items-start gap-2 rounded-md p-3 text-sm"
            >
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {warning}
            </p>
          ))}

          {/* Mention imposée par la spec 01 §3. */}
          <p className="text-muted-foreground flex items-start gap-2 text-xs">
            <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            {estimate.notice}
          </p>
        </>
      )}

      {manual ? (
        <NumberField
          label="Objectif calorique"
          unit="kcal"
          step="1"
          registration={register('daily_calories')}
          error={errors.daily_calories}
        />
      ) : (
        <Button
          type="button"
          variant="outline"
          className="self-start"
          onClick={() => setManual(true)}
        >
          <RefreshCw aria-hidden="true" />
          Définir moi-même mes calories
        </Button>
      )}
    </div>
  )
}
