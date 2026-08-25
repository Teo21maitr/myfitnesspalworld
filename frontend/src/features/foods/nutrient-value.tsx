import { cn } from '@/lib/utils'

interface NutrientValueProps {
  value: string | null
  unit: string
  className?: string
}

/**
 * Affiche une valeur nutritionnelle.
 *
 * Une valeur inconnue s'affiche « — » et jamais 0 : la distinction est une
 * règle métier, pas une préférence de présentation (spec 01 §8).
 */
export function NutrientValue({ value, unit, className }: NutrientValueProps) {
  if (value === null || value === undefined) {
    return (
      <span className={cn('text-muted-foreground', className)} title="Donnée non renseignée">
        —
      </span>
    )
  }

  const rounded = Math.round(Number(value) * 10) / 10

  return (
    <span className={cn('tabular-nums', className)}>
      {rounded.toLocaleString('fr-FR')}
      <span className="text-muted-foreground ml-0.5 text-xs">{unit}</span>
    </span>
  )
}
