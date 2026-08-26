import { CalendarPlus, ChevronLeft, ChevronRight, TriangleAlert, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { formatDate, shift, today } from '@/features/diary/dates'
import { CopyDialog } from '@/features/diary/copy-dialog'
import { MealCard } from '@/features/diary/meal-card'
import { useCopyDay, useDiaryDay } from '@/features/diary/use-diary'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { DiaryDay } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

/** Les quatre valeurs suivies au quotidien, dans l'ordre du dashboard. */
const SUMMARY = [
  { key: 'energy_kcal', goal: 'daily_calories', label: 'Calories', unit: 'kcal' },
  { key: 'protein_g', goal: 'protein_g', label: 'Protéines', unit: 'g' },
  { key: 'carbohydrates_g', goal: 'carbs_g', label: 'Glucides', unit: 'g' },
  { key: 'fat_g', goal: 'fat_g', label: 'Lipides', unit: 'g' },
] as const

function DaySummary({ day }: { day: DiaryDay }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle as="h2" className="text-base">
          Bilan du jour
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {SUMMARY.map(({ key, goal, label, unit }) => (
            <div key={key} className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">{label}</dt>
              <dd className="text-lg font-semibold">
                <NutrientValue value={day.totals[key]} unit={unit} />
              </dd>
              {day.goals && (
                <p className="text-muted-foreground text-xs">
                  objectif <NutrientValue value={day.goals[goal]} unit={unit} />
                </p>
              )}
            </div>
          ))}
        </dl>

        {day.incomplete_nutrients.length > 0 && (
          <p className="text-muted-foreground mt-3 text-xs">
            * Certaines valeurs ne sont pas renseignées : les totaux marqués sont partiels.
          </p>
        )}

        {!day.goals && (
          <p className="text-muted-foreground mt-3 text-xs">
            Aucun objectif défini pour cette date.{' '}
            <Link to="/objectifs" className="underline">
              Définir un objectif
            </Link>
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function JournalPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const date = searchParams.get('date') ?? today()
  const { data: day, error, isPending } = useDiaryDay(date)
  const [copying, setCopying] = useState(false)
  const copy = useCopyDay()

  const hasEntries = (day?.meals ?? []).some((section) => section.entries.length > 0)

  const goTo = (next: string) => setSearchParams({ date: next }, { replace: true })

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Journal</h1>
          <p className="text-muted-foreground mt-1 text-sm first-letter:uppercase">
            {formatDate(date)}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {hasEntries && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-expanded={copying}
              onClick={() => setCopying((value) => !value)}
            >
              <CalendarPlus aria-hidden="true" className="size-4" />
              Copier la journée
            </Button>
          )}
          <Button asChild variant="outline" size="sm">
            <Link to={`/ajout-rapide?date=${date}`}>
              <Zap aria-hidden="true" className="size-4" />
              Ajout rapide
            </Link>
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          size="icon"
          variant="outline"
          onClick={() => goTo(shift(date, -1))}
          aria-label="Jour précédent"
        >
          <ChevronLeft aria-hidden="true" className="size-4" />
        </Button>

        <Input
          type="date"
          aria-label="Date du journal"
          className="flex-1"
          value={date}
          onChange={(event) => event.target.value && goTo(event.target.value)}
        />

        <Button
          type="button"
          size="icon"
          variant="outline"
          onClick={() => goTo(shift(date, 1))}
          aria-label="Jour suivant"
        >
          <ChevronRight aria-hidden="true" className="size-4" />
        </Button>

        {date !== today() && (
          <Button type="button" variant="ghost" size="sm" onClick={() => goTo(today())}>
            Aujourd’hui
          </Button>
        )}
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <div className="bg-muted h-28 animate-pulse rounded-xl" />
          <div className="bg-muted h-40 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement du journal…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {copying && (
        <CopyDialog
          title="Copier cette journée"
          description="Chaque entrée retrouve son repas. Les journées cibles gardent ce qu'elles contiennent déjà."
          isPending={copy.isPending}
          error={copy.error}
          onClose={() => setCopying(false)}
          onCopy={(dates) => copy.mutateAsync({ source_date: date, target_dates: dates })}
        />
      )}

      {day && (
        <>
          <DaySummary day={day} />
          {/* `Array.isArray` plutôt qu'un accès direct : une réponse tronquée
              doit dégrader la page, pas la faire tomber. */}
          {(Array.isArray(day.meals) ? day.meals : []).map((section) => (
            <MealCard key={section.meal_type.id} section={section} date={date} />
          ))}
        </>
      )}
    </div>
  )
}
