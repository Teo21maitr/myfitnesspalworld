import { ArrowLeft, TriangleAlert } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { shift, today } from '@/features/diary/dates'
import { ProgressChart } from '@/features/progress/weight-chart'
import { useSharedChart } from '@/features/shares/use-shares'
import { describeError } from '@/lib/query-client'

const CHART_PERIOD_DAYS = 90

/** Progression d'un ami, en lecture seule (spec 05 §9). */
export function SharedProgressPage() {
  const params = useParams()
  const userId = Number(params.userId)

  const to = today()
  const from = shift(to, -(CHART_PERIOD_DAYS - 1))
  const { data: series, error, isPending } = useSharedChart(userId, 'weight', from, to)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/amis">
            <ArrowLeft aria-hidden="true" />
            Amis
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Progression partagée</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Consultation seule. Les photos de progression ne sont jamais partagées.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Poids
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-40 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement de la courbe…</span>
            </div>
          )}
          {error && (
            <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {describeError(error)}
            </p>
          )}
          {series && <ProgressChart series={series} label="Poids" />}
        </CardContent>
      </Card>
    </div>
  )
}
