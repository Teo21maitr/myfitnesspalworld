import { cn } from '@/lib/utils'

/** Nom lisible de chaque objectif. */
const LABELS: Record<string, string> = {
  daily_calories: 'Calories',
  protein_g: 'Protéines',
  carbs_g: 'Glucides',
  fat_g: 'Lipides',
}

/**
 * Écart d'une journée à ses objectifs.
 *
 * Le chiffre affiché est celui qui a servi à décider : mesuré sur les fiches de
 * la base, pas sur ce que le modèle a annoncé. Le respect des tolérances vient
 * du serveur — les seuils recopiés ici finiraient par diverger de la
 * spec 01 §15.
 */
export function Deviations({
  deviations,
  withinTolerance,
}: {
  deviations: Record<string, number>
  withinTolerance: boolean
}) {
  const entries = Object.entries(deviations)
  if (entries.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
      {entries.map(([name, value]) => (
        <span key={name} className="tabular-nums">
          <span className="text-muted-foreground">{LABELS[name] ?? name} </span>
          <span className={cn(!withinTolerance && Math.abs(value) > 0 && 'font-medium')}>
            {value > 0 ? '+' : ''}
            {value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %
          </span>
        </span>
      ))}
      {!withinTolerance && (
        <span className="text-muted-foreground">hors tolérance après correction</span>
      )}
    </div>
  )
}
