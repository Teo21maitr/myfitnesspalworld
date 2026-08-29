import { ChevronLeft, ChevronRight, Loader2, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { MacroValues } from '@/lib/api/types'

import { Deviations } from './deviation'

/** Forme commune à une journée proposée et à une journée enregistrée. */
export interface DayView {
  date: string
  totals: MacroValues
  deviations: Record<string, number>
  within_tolerance: boolean
  unmatched?: string[]
  meals: { meal: string; meal_type_id: number | null; items: DayItem[] }[]
}

export interface DayItem {
  label: string
  quantity: string
  unit_label: string
  values: MacroValues
  /** Vrai pour une recette que le modèle a inventée et qui n'existe pas encore. */
  isNewRecipe?: boolean
}

function formatQuantity(quantity: string, unit: string): string {
  return `${Number(quantity).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} ${unit}`
}

export function PlanDay({
  day,
  index,
  total,
  onPrevious,
  onNext,
  onRegenerate,
  regenerating,
}: {
  day: DayView
  index: number
  total: number
  onPrevious: () => void
  onNext: () => void
  onRegenerate?: (mealTypeId: number) => void
  regenerating?: number | null
}) {
  const date = new Date(`${day.date}T12:00:00`)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Journée précédente"
          disabled={index === 0}
          onClick={onPrevious}
        >
          <ChevronLeft aria-hidden="true" className="size-4" />
        </Button>
        <div className="text-center">
          <p className="font-medium capitalize">
            {date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
          <p className="text-muted-foreground text-xs">
            Jour {index + 1} sur {total}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Journée suivante"
          disabled={index >= total - 1}
          onClick={onNext}
        >
          <ChevronRight aria-hidden="true" className="size-4" />
        </Button>
      </div>

      <div className="rounded-lg border p-3">
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <span>
            <NutrientValue value={day.totals.energy_kcal} unit="kcal" />
          </span>
          <span>
            P <NutrientValue value={day.totals.protein_g} unit="g" />
          </span>
          <span>
            G <NutrientValue value={day.totals.carbohydrates_g} unit="g" />
          </span>
          <span>
            L <NutrientValue value={day.totals.fat_g} unit="g" />
          </span>
        </div>
        <div className="mt-2">
          <Deviations deviations={day.deviations} withinTolerance={day.within_tolerance} />
        </div>
      </div>

      {day.unmatched && day.unmatched.length > 0 && (
        <p className="text-muted-foreground text-sm">
          Non retrouvés dans la base, et donc écartés : {day.unmatched.join(', ')}.
        </p>
      )}

      <ul className="space-y-3">
        {day.meals.map((meal) => (
          <li key={meal.meal} className="rounded-xl border p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium">{meal.meal}</p>
              {onRegenerate && meal.meal_type_id !== null && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Régénérer ${meal.meal}`}
                  disabled={regenerating !== null && regenerating !== undefined}
                  onClick={() => onRegenerate(meal.meal_type_id as number)}
                >
                  {regenerating === meal.meal_type_id ? (
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                  ) : (
                    <RefreshCw aria-hidden="true" className="size-4" />
                  )}
                  Régénérer
                </Button>
              )}
            </div>

            {meal.items.length === 0 ? (
              <p className="text-muted-foreground mt-2 text-sm">Rien de prévu.</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {meal.items.map((item, position) => (
                  <li
                    key={`${item.label}-${position}`}
                    className="flex items-baseline justify-between gap-3 text-sm"
                  >
                    <span>
                      {item.label}
                      {item.isNewRecipe && (
                        <span className="text-muted-foreground ml-2 text-xs">nouvelle recette</span>
                      )}
                    </span>
                    <span className="text-muted-foreground shrink-0 tabular-nums">
                      {formatQuantity(item.quantity, item.unit_label)} ·{' '}
                      <NutrientValue value={item.values.energy_kcal} unit="kcal" />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
