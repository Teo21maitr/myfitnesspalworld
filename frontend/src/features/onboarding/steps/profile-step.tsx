import { useFormContext } from 'react-hook-form'

import { NumberField } from '@/components/form/number-field'
import { SelectField } from '@/components/form/select-field'
import { TextField } from '@/components/form/text-field'

import { SEX_OPTIONS, type OnboardingValues } from '../schema'

/** Étape 1 — informations personnelles (spec 01 §2). */
export function ProfileStep() {
  const {
    register,
    formState: { errors },
  } = useFormContext<OnboardingValues>()

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Ces informations servent uniquement à estimer vos besoins énergétiques.
      </p>

      <TextField
        label="Date de naissance"
        type="date"
        autoComplete="bday"
        registration={register('birth_date')}
        error={errors.birth_date}
      />

      <SelectField
        label="Sexe utilisé pour le calcul"
        options={SEX_OPTIONS}
        hint="La formule métabolique standard distingue deux profils."
        registration={register('sex_for_calculation')}
        error={errors.sex_for_calculation}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <NumberField
          label="Taille"
          unit="cm"
          step="0.1"
          registration={register('height_cm')}
          error={errors.height_cm}
        />
        <NumberField
          label="Poids actuel"
          unit="kg"
          step="0.1"
          registration={register('weight_kg')}
          error={errors.weight_kg}
        />
      </div>
    </div>
  )
}
