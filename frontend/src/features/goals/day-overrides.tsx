import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { NutritionGoal } from '@/lib/api/types'
import { cn } from '@/lib/utils'

import { useDeleteDayOverride, useSetDayOverride } from './use-goals'

/** Convention Python : lundi vaut 0, dimanche 6. */
const WEEKDAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

/** Surcharges d'objectif par jour de la semaine (spec 01 §4). */
export function DayOverrides({ goal }: { goal: NutritionGoal }) {
  const [selected, setSelected] = useState<number | null>(null)
  const [calories, setCalories] = useState('')

  const save = useSetDayOverride(goal.id)
  const remove = useDeleteDayOverride(goal.id)

  const overrideFor = (weekday: number) =>
    goal.day_overrides.find((override) => override.weekday === weekday)

  const openEditor = (weekday: number) => {
    const existing = overrideFor(weekday)
    setSelected(weekday)
    setCalories(existing?.daily_calories ? String(Math.round(Number(existing.daily_calories))) : '')
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Par défaut, le même objectif s’applique chaque jour. Vous pouvez le remplacer pour certains
        jours de la semaine.
      </p>

      <ul className="flex flex-wrap gap-2">
        {WEEKDAYS.map((label, weekday) => {
          const override = overrideFor(weekday)
          return (
            <li key={label}>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-pressed={selected === weekday}
                onClick={() => openEditor(weekday)}
                className={cn(override && 'border-primary text-primary')}
              >
                {label}
                {override?.daily_calories && (
                  <span className="text-muted-foreground ml-1 tabular-nums">
                    {Math.round(Number(override.daily_calories))}
                  </span>
                )}
              </Button>
            </li>
          )
        })}
      </ul>

      {selected !== null && (
        <div className="flex flex-col gap-3 rounded-lg border p-4">
          <Label htmlFor="override-calories">Calories du {WEEKDAYS[selected]?.toLowerCase()}</Label>
          <Input
            id="override-calories"
            type="number"
            inputMode="decimal"
            value={calories}
            placeholder={String(Math.round(Number(goal.daily_calories)))}
            onChange={(event) => setCalories(event.target.value)}
          />

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              disabled={!calories || save.isPending}
              onClick={() =>
                save
                  .mutateAsync({ weekday: selected, values: { daily_calories: calories } })
                  .then(() => {
                    toast.success('Surcharge enregistrée.')
                    setSelected(null)
                  })
                  .catch(() => undefined)
              }
            >
              Enregistrer la surcharge
            </Button>

            {overrideFor(selected) && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={remove.isPending}
                onClick={() =>
                  remove
                    .mutateAsync(selected)
                    .then(() => {
                      toast.success('Surcharge supprimée.')
                      setSelected(null)
                    })
                    .catch(() => undefined)
                }
              >
                Supprimer la surcharge
              </Button>
            )}

            <Button type="button" size="sm" variant="ghost" onClick={() => setSelected(null)}>
              Annuler
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
