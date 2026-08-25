import { Controller, useFormContext } from 'react-hook-form'

import { OptionCards } from '@/components/form/option-cards'

import { ACTIVITY_OPTIONS, type OnboardingValues } from '../schema'

/** Étape 3 — niveau d'activité (spec 01 §2). */
export function ActivityStep() {
  const {
    control,
    formState: { errors },
  } = useFormContext<OnboardingValues>()

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Le niveau d’activité sert uniquement au calcul initial : l’application ne suit pas les
        exercices.
      </p>

      <Controller
        control={control}
        name="activity_level"
        render={({ field }) => (
          <OptionCards
            legend="À quel point êtes-vous actif au quotidien ?"
            name={field.name}
            options={ACTIVITY_OPTIONS}
            value={field.value}
            onChange={field.onChange}
            error={errors.activity_level}
          />
        )}
      />
    </div>
  )
}
