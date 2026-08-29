import { ArrowLeft, ChevronLeft, ChevronRight, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, shift, today } from '@/features/diary/dates'
import { NutrientValue } from '@/features/foods/nutrient-value'
import { useSharedDiary } from '@/features/shares/use-shares'
import { describeError } from '@/lib/query-client'

import { useSharedOwner } from './use-shared-owner'

/**
 * Journal d'un ami, en lecture seule (spec 05 §8).
 *
 * Aucune action d'écriture n'est proposée : ni bouton, ni menu. Le backend
 * refuserait, mais offrir une action vouée au refus est déjà un défaut.
 */
export function SharedDiaryPage() {
  const { userId, name, invalid } = useSharedOwner()
  const [date, setDate] = useState(today())

  const { data: day, error, isPending } = useSharedDiary(userId, date)
  const meals = Array.isArray(day?.meals) ? day.meals : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/amis">
            <ArrowLeft aria-hidden="true" />
            Amis
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">
          {name ? `Journal de ${name}` : 'Journal partagé'}
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">Consultation seule.</p>
      </div>

      {/* Une adresse malformée laissait la requête désactivée, donc un
          squelette qui ne se résolvait jamais. */}
      {invalid && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          Cette adresse ne désigne aucun compte.
        </p>
      )}

      <div className="flex items-center justify-between gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Jour précédent"
          onClick={() => setDate((current) => shift(current, -1))}
        >
          <ChevronLeft aria-hidden="true" className="size-4" />
        </Button>
        <span className="text-sm first-letter:uppercase">{formatDate(date)}</span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Jour suivant"
          onClick={() => setDate((current) => shift(current, 1))}
        >
          <ChevronRight aria-hidden="true" className="size-4" />
        </Button>
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <div className="bg-muted h-24 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement du journal…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {day && (
        <>
          <Card>
            <CardHeader>
              <CardTitle as="h2" className="text-base">
                Total du jour
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold">
                <NutrientValue value={day.totals.energy_kcal} unit="kcal" />
              </p>
              {day.incomplete_nutrients.length > 0 && (
                <p className="text-muted-foreground mt-1 text-xs">
                  Total partiel : certaines valeurs ne sont pas renseignées.
                </p>
              )}
            </CardContent>
          </Card>

          {meals.map((section) => (
            <Card key={section.meal_type.id}>
              <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
                <CardTitle as="h2" className="text-base">
                  {section.meal_type.name}
                </CardTitle>
                <span className="text-muted-foreground text-sm">
                  <NutrientValue value={section.totals.energy_kcal} unit="kcal" />
                </span>
              </CardHeader>
              <CardContent>
                {section.entries.length === 0 ? (
                  <p className="text-muted-foreground text-sm">Rien pour ce repas.</p>
                ) : (
                  <ul className="flex flex-col">
                    {section.entries.map((entry) => (
                      <li
                        key={entry.id}
                        className="flex items-baseline justify-between gap-4 border-b py-2 last:border-b-0"
                      >
                        <span className="flex flex-col">
                          <span className="text-sm">{entry.snapshot_name}</span>
                          <span className="text-muted-foreground text-xs">
                            {Number(entry.quantity).toLocaleString('fr-FR')} {entry.unit_label}
                          </span>
                        </span>
                        <span className="text-sm font-medium">
                          <NutrientValue value={entry.computed.energy_kcal} unit="kcal" />
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </>
      )}
    </div>
  )
}
