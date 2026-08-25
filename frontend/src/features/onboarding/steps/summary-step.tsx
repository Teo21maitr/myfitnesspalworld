import { useFormContext } from 'react-hook-form'

import { ACTIVITY_LABELS, GOAL_LABELS, SEX_LABELS, type OnboardingValues } from '../schema'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b py-2 last:border-b-0">
      <dt className="text-muted-foreground text-sm">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  )
}

/** Étape 7 — récapitulatif avant enregistrement (spec 01 §2). */
export function SummaryStep() {
  const { getValues } = useFormContext<OnboardingValues>()
  const values = getValues()

  const rate = values.goal_rate_kg_per_week
    ? `${Number(values.goal_rate_kg_per_week).toLocaleString('fr-FR')} kg / semaine`
    : 'Non applicable'

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold">Vos informations</h2>
        <dl>
          <Row label="Date de naissance" value={values.birth_date} />
          <Row label="Sexe utilisé pour le calcul" value={SEX_LABELS[values.sex_for_calculation]} />
          <Row label="Taille" value={`${values.height_cm} cm`} />
          <Row label="Poids actuel" value={`${values.weight_kg} kg`} />
          <Row label="Objectif" value={GOAL_LABELS[values.goal_type]} />
          {values.target_weight_kg && (
            <Row label="Poids cible" value={`${values.target_weight_kg} kg`} />
          )}
          <Row label="Niveau d’activité" value={ACTIVITY_LABELS[values.activity_level]} />
          <Row label="Rythme" value={rate} />
        </dl>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold">Vos objectifs quotidiens</h2>
        <dl>
          <Row label="Calories" value={`${values.daily_calories} kcal`} />
          <Row label="Protéines" value={`${values.protein_g} g`} />
          <Row label="Glucides" value={`${values.carbs_g} g`} />
          <Row label="Lipides" value={`${values.fat_g} g`} />
        </dl>
      </section>

      <p className="text-muted-foreground text-xs">
        Ces objectifs restent modifiables à tout moment depuis la page Objectifs.
      </p>
    </div>
  )
}
