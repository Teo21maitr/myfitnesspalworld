import { Controller, useFormContext, useWatch } from 'react-hook-form'

import { OptionCards } from '@/components/form/option-cards'

import { RATE_OPTIONS, type OnboardingValues } from '../schema'

/** Étape 4 — rythme de perte ou de prise (spec 01 §2). */
export function RateStep() {
  const {
    control,
    formState: { errors },
  } = useFormContext<OnboardingValues>()

  const goalType = useWatch({ control, name: 'goal_type' })

  if (goalType === 'MAINTENANCE') {
    return (
      <p className="text-muted-foreground text-sm">
        Vous visez le maintien de votre poids : aucun rythme n’est nécessaire, votre objectif
        correspondra à votre dépense énergétique estimée.
      </p>
    )
  }

  const verb = goalType === 'LOSS' ? 'perdre' : 'prendre'

  return (
    <div className="flex flex-col gap-4">
      <Controller
        control={control}
        name="goal_rate_kg_per_week"
        render={({ field }) => (
          <OptionCards
            legend={`À quelle vitesse souhaitez-vous ${verb} du poids ?`}
            name={field.name}
            options={RATE_OPTIONS}
            value={field.value}
            onChange={field.onChange}
            error={errors.goal_rate_kg_per_week}
          />
        )}
      />
    </div>
  )
}
