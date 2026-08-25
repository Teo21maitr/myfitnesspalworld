import { TriangleAlert } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DayOverrides } from '@/features/goals/day-overrides'
import { GoalForm } from '@/features/goals/goal-form'
import { GoalSummary } from '@/features/goals/goal-summary'
import { useCurrentGoal, useGoalHistory } from '@/features/goals/use-goals'
import { describeError } from '@/lib/query-client'
import type { NutritionGoal } from '@/lib/api/types'

function formatPeriod(goal: NutritionGoal): string {
  const start = new Date(goal.start_date).toLocaleDateString('fr-FR')
  if (!goal.end_date) return `depuis le ${start}`
  return `du ${start} au ${new Date(goal.end_date).toLocaleDateString('fr-FR')}`
}

export function GoalsPage() {
  const { data: current, error, isPending } = useCurrentGoal()
  const history = useGoalHistory()

  const past = (history.data?.results ?? []).filter((goal) => !goal.is_current)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Objectifs</h1>
        <p className="text-muted-foreground mt-1 text-sm">Vos apports quotidiens de référence.</p>
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-2">
          <div className="bg-muted h-20 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement de vos objectifs…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {current === null && !isPending && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Aucun objectif</CardTitle>
            <CardDescription>
              Aucun objectif nutritionnel n’est défini pour le moment.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {current && (
        <>
          <Card>
            <CardHeader>
              <CardTitle as="h2">Aujourd’hui</CardTitle>
              <CardDescription>Objectif applicable {formatPeriod(current.goal)}.</CardDescription>
            </CardHeader>
            <CardContent>
              <GoalSummary current={current} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle as="h2">Modifier mes objectifs</CardTitle>
              <CardDescription>
                Les modifications ne s’appliquent pas aux journées déjà passées.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <GoalForm goal={current.goal} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle as="h2">Jours particuliers</CardTitle>
              <CardDescription>Un objectif différent selon le jour de la semaine.</CardDescription>
            </CardHeader>
            <CardContent>
              <DayOverrides goal={current.goal} />
            </CardContent>
          </Card>
        </>
      )}

      {past.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Historique</CardTitle>
            <CardDescription>Vos objectifs précédents, conservés tels quels.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col">
              {past.map((goal) => (
                <li
                  key={goal.id}
                  className="flex items-baseline justify-between gap-4 border-b py-2 last:border-b-0"
                >
                  <span className="text-muted-foreground text-sm">{formatPeriod(goal)}</span>
                  <span className="text-sm font-medium tabular-nums">
                    {Math.round(Number(goal.daily_calories))} kcal
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
