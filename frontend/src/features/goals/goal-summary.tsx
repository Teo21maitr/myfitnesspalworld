import type { CurrentGoal } from '@/lib/api/types'

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className="text-lg font-semibold tabular-nums">
        {Math.round(Number(value))}
        <span className="text-muted-foreground ml-1 text-xs font-normal">{unit}</span>
      </span>
    </div>
  )
}

/** Valeurs applicables aujourd'hui, surcharge du jour comprise. */
export function GoalSummary({ current }: { current: CurrentGoal }) {
  const { today, goal } = current
  // Comparaison numérique : « 2209 » et « 2209.00 » désignent la même valeur.
  const overridden = Number(today.daily_calories) !== Number(goal.daily_calories)

  return (
    <div data-testid="goal-summary" className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Calories" value={today.daily_calories} unit="kcal" />
        <Metric label="Protéines" value={today.protein_g} unit="g" />
        <Metric label="Glucides" value={today.carbs_g} unit="g" />
        <Metric label="Lipides" value={today.fat_g} unit="g" />
      </div>

      {overridden && (
        <p className="text-muted-foreground text-xs">
          Une surcharge est active aujourd’hui : l’objectif de base est de{' '}
          {Math.round(Number(goal.daily_calories))} kcal.
        </p>
      )}
    </div>
  )
}
