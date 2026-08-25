import { Controller, useFormContext, useWatch } from 'react-hook-form'

import { NumberField } from '@/components/form/number-field'
import { OptionCards } from '@/components/form/option-cards'

import { GOAL_OPTIONS, type OnboardingValues } from '../schema'

/** Étape 2 — objectif de poids (spec 01 §2). */
export function GoalStep() {
  const {
    control,
    register,
    formState: { errors },
  } = useFormContext<OnboardingValues>()

  const goalType = useWatch({ control, name: 'goal_type' })

  return (
    <div className="flex flex-col gap-4">
      <Controller
        control={control}
        name="goal_type"
        render={({ field }) => (
          <OptionCards
            legend="Quel est votre objectif ?"
            name={field.name}
            options={GOAL_OPTIONS}
            value={field.value}
            onChange={field.onChange}
            error={errors.goal_type}
          />
        )}
      />

      {goalType !== 'MAINTENANCE' && (
        <NumberField
          label="Poids cible (facultatif)"
          unit="kg"
          step="0.1"
          hint="Sert uniquement de repère : il n’entre pas dans le calcul des calories."
          registration={register('target_weight_kg')}
          error={errors.target_weight_kg}
        />
      )}
    </div>
  )
}
