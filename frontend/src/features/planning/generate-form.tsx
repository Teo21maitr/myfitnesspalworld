import { Loader2, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import { activeMeals } from '@/features/diary/meals'
import { useMealTypes } from '@/features/diary/use-diary'
import type { GenerateConstraints } from './api'

/**
 * Aligné sur la limite du backend.
 *
 * Sept jours : ce que la spec 01 §15 demande, et ce que le temps permet — une
 * journée coûte jusqu'à une minute quand elle demande ses trois essais.
 */
const MAX_DAYS = 7

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
}

/**
 * Contraintes de génération (spec 01 §15).
 *
 * Le budget, le temps de préparation et le régime alimentaire n'y figurent
 * pas : la spec les exclut explicitement.
 */
export function GenerateForm({
  onGenerate,
  pending,
}: {
  onGenerate: (constraints: GenerateConstraints) => void
  pending: boolean
}) {
  const mealTypes = useMealTypes()
  const meals = activeMeals(mealTypes.data)

  const [start, setStart] = useState(today)
  const [days, setDays] = useState('7')
  const [selected, setSelected] = useState<number[] | null>(null)
  const [allergies, setAllergies] = useState('')
  const [liked, setLiked] = useState('')
  const [disliked, setDisliked] = useState('')

  // Tous les repas actifs par défaut, sans attendre que la requête réponde.
  const chosen = selected ?? meals.map((meal) => meal.id)
  const count = Math.min(Math.max(Number(days) || 1, 1), MAX_DAYS)

  const toggle = (id: number, checked: boolean) =>
    setSelected(chosen.filter((value) => value !== id).concat(checked ? [id] : []))

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="plan-start">Premier jour</Label>
          <Input
            id="plan-start"
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="plan-days">Nombre de jours</Label>
          <Input
            id="plan-days"
            type="number"
            min={1}
            max={MAX_DAYS}
            value={days}
            onChange={(event) => setDays(event.target.value)}
          />
        </div>
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-medium">Repas à remplir</legend>
        <ul className="grid grid-cols-2 gap-2">
          {meals.map((meal) => (
            <li key={meal.id}>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={chosen.includes(meal.id)}
                  onChange={(event) => toggle(meal.id, event.target.checked)}
                />
                {meal.name}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="plan-allergies">Allergies</Label>
          <Input
            id="plan-allergies"
            placeholder="arachide, gluten"
            value={allergies}
            onChange={(event) => setAllergies(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="plan-liked">Aliments aimés</Label>
          <Input
            id="plan-liked"
            placeholder="saumon, avocat"
            value={liked}
            onChange={(event) => setLiked(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="plan-disliked">Aliments détestés</Label>
          <Input
            id="plan-disliked"
            placeholder="courgette"
            value={disliked}
            onChange={(event) => setDisliked(event.target.value)}
          />
        </div>
      </div>

      <p className="text-muted-foreground text-xs">
        Chaque journée demande un appel au modèle, parfois trois quand elle sort des tolérances.
        Comptez jusqu’à une minute par jour.
      </p>

      <Button
        type="button"
        className="w-full"
        disabled={pending || chosen.length === 0}
        onClick={() =>
          onGenerate({
            start_date: start,
            end_date: addDays(start, count - 1),
            meal_type_ids: chosen,
            allergies: splitList(allergies),
            liked: splitList(liked),
            disliked: splitList(disliked),
          })
        }
      >
        {pending ? (
          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
        ) : (
          <Sparkles aria-hidden="true" className="size-4" />
        )}
        Composer le plan
      </Button>
    </div>
  )
}
