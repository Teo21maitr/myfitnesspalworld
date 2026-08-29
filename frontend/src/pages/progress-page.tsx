import { TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'

import { SelectField } from '@/components/form/select-field'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { shift, today } from '@/features/diary/dates'
import { MeasurementHistory, WeightHistory } from '@/features/progress/history-list'
import { MeasurementForm } from '@/features/progress/measurement-form'
import { METRIC_OPTIONS, metricLabel } from '@/features/progress/metrics'
import { useChart, useMeasurements, useWeightEntries } from '@/features/progress/use-progress'
import { ProgressChart } from '@/features/progress/weight-chart'
import { WeightForm } from '@/features/progress/weight-form'
import type { ChartMetric } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

/** Fenêtre affichée par défaut, identique à celle du backend (spec 04 §14). */
const CHART_PERIOD_DAYS = 90

function ErrorLine({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {describeError(error)}
    </p>
  )
}

/**
 * Progression (spec 01 §19).
 *
 * Les photos de progression (spec 01 §20) demandent le stockage objet et ne
 * figurent pas encore sur cet écran.
 */
export function ProgressPage() {
  const to = today()
  const from = shift(to, -(CHART_PERIOD_DAYS - 1))

  const [metric, setMetric] = useState<ChartMetric>('weight')

  const chart = useChart(metric, from, to)
  const weights = useWeightEntries()
  const measurements = useMeasurements()

  // `Array.isArray` plutôt qu'un simple `??` : une réponse de forme
  // inattendue doit dégrader l'écran, pas le faire tomber.
  const weightEntries = useMemo(
    () => (Array.isArray(weights.data?.results) ? weights.data.results : []),
    [weights.data],
  )
  const measurementEntries = useMemo(
    () => (Array.isArray(measurements.data?.results) ? measurements.data.results : []),
    [measurements.data],
  )

  // Les dates déjà pesées, telles que l'historique affiché juste dessous les
  // montre : le formulaire annonce « Mettre à jour » pour exactement celles
  // que l'utilisateur a sous les yeux.
  const measuredDates = useMemo(
    () => new Set(weightEntries.map((entry) => entry.date)),
    [weightEntries],
  )

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Progression</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Pesées, mensurations et tendance sur les trois derniers mois.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Enregistrer une pesée
          </CardTitle>
          <CardDescription>Une seule pesée par date : la dernière saisie fait foi.</CardDescription>
        </CardHeader>
        <CardContent>
          <WeightForm measuredDates={measuredDates} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3">
          <CardTitle as="h2" className="text-base">
            Courbe
          </CardTitle>
          <SelectField
            label="Mesure affichée"
            options={METRIC_OPTIONS}
            value={metric}
            onChange={(event) => setMetric(event.target.value as ChartMetric)}
          />
        </CardHeader>
        <CardContent>
          {chart.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-40 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement de la courbe…</span>
            </div>
          )}
          {chart.error && <ErrorLine error={chart.error} />}
          {chart.data && <ProgressChart series={chart.data} label={metricLabel(metric)} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Mensurations
          </CardTitle>
          <CardDescription>Toutes facultatives, une entrée par date.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <MeasurementForm entries={measurementEntries} />

          {measurements.error ? (
            <ErrorLine error={measurements.error} />
          ) : (
            !measurements.isPending && <MeasurementHistory entries={measurementEntries} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Historique des pesées
          </CardTitle>
        </CardHeader>
        <CardContent>
          {weights.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-24 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement de l’historique…</span>
            </div>
          )}
          {weights.error && <ErrorLine error={weights.error} />}
          {weights.data && <WeightHistory entries={weightEntries} />}
        </CardContent>
      </Card>
    </div>
  )
}
