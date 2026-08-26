import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { MealSection } from '@/lib/api/types'

import { EntryRow } from './entry-row'

/** Un repas de la journée, ses entrées et son sous-total (spec 06 §6). */
export function MealCard({ section, date }: { section: MealSection; date: string }) {
  const { meal_type: mealType, entries, totals, incomplete_nutrients: incomplete } = section
  const isPartial = incomplete.includes('energy_kcal')

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
        <CardTitle as="h2" className="text-base">
          {mealType.name}
        </CardTitle>
        <span className="text-sm font-medium">
          <NutrientValue value={totals.energy_kcal} unit="kcal" />
          {isPartial && (
            <span
              className="text-muted-foreground ml-1"
              title="Certaines valeurs ne sont pas renseignées : ce total est partiel."
            >
              *
            </span>
          )}
        </span>
      </CardHeader>

      <CardContent className="flex flex-col gap-2">
        {entries.length === 0 ? (
          <p className="text-muted-foreground text-sm">Rien pour l’instant.</p>
        ) : (
          <ul className="flex flex-col">
            {entries.map((entry) => (
              <EntryRow key={entry.id} entry={entry} />
            ))}
          </ul>
        )}

        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={`/aliments?repas=${mealType.id}&date=${date}`}>
            <Plus aria-hidden="true" className="size-4" />
            Ajouter un aliment
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}
