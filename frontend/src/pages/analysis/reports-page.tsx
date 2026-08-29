import { Download, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExportFormat } from '@/features/analysis/api'
import { DEFAULT_PERIOD, PERIOD_OPTIONS, periodRange } from '@/features/analysis/period'
import { useReport, useReportExport } from '@/features/analysis/use-analysis'
import { NUTRIENT_LABELS } from '@/features/foods/nutrients'
import { ProgressChart } from '@/features/progress/weight-chart'
import type { PeriodReport } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

/** Ce que le résumé met en avant, dans le même ordre que le PDF. */
const SUMMARY_NUTRIENTS = ['energy_kcal', 'protein_g', 'carbohydrates_g', 'fat_g', 'fiber_g']

function formatAmount(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 1 })
}

function Averages({ report }: { report: PeriodReport }) {
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {SUMMARY_NUTRIENTS.map((key) => (
        <div key={key} className="rounded-md border p-3">
          <dt className="text-muted-foreground text-xs">{NUTRIENT_LABELS[key] ?? key}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">
            {formatAmount(report.averages?.[key])}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function Summary({ report }: { report: PeriodReport }) {
  const measured = report.adherence?.days_measured ?? 0
  const within = report.adherence?.days_within_goal ?? 0
  const points = Array.isArray(report.weight?.points) ? report.weight.points : []

  if (report.logged_days === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Aucune journée journalisée sur cette période. Rien à moyenner : ce n’est pas la même chose
        que zéro.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Moyennes calculées sur{' '}
        <strong className="text-foreground">
          {report.logged_days} journée{report.logged_days > 1 ? 's' : ''} journalisée
          {report.logged_days > 1 ? 's' : ''}
        </strong>
        , parmi les {report.calendar_days} jours de la période.
      </p>

      <Averages report={report} />

      <p className="text-sm">
        {measured === 0 ? (
          <span className="text-muted-foreground">
            Aucun objectif applicable sur la période : le respect ne peut pas être mesuré.
          </span>
        ) : (
          <>
            Objectif calorique respecté{' '}
            <strong>
              {within} journée{within > 1 ? 's' : ''} sur {measured}
            </strong>
            .
          </>
        )}
      </p>

      <div>
        <h3 className="mb-2 text-sm font-medium">Poids</h3>
        {points.length === 0 ? (
          <p className="text-muted-foreground text-sm">Aucune pesée sur cette période.</p>
        ) : (
          <>
            <p className="text-muted-foreground mb-2 text-sm">
              {report.weight_change === null
                ? 'Une seule pesée : pas encore de variation.'
                : `${formatAmount(report.weight_change)} kg sur la période.`}
            </p>
            <ProgressChart
              series={{
                metric: 'weight',
                unit: 'kg',
                from: report.from,
                to: report.to,
                points,
                target: report.weight.target,
                trend_per_week: report.weight.trend_per_week,
              }}
              label="Poids"
            />
          </>
        )}
      </div>
    </div>
  )
}

/** Rapports : résumé de période et exports CSV/PDF (spec 01 §22). */
export function ReportsPage() {
  const [period, setPeriod] = useState<string>(DEFAULT_PERIOD)

  const { from, to } = periodRange(period)
  const report = useReport(from, to)
  const exporter = useReportExport(from, to)

  const download = (format: ExportFormat) => () => exporter.mutate(format)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Rapports</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Résumé d’une période, et son export pour l’emporter ailleurs.
        </p>
      </div>

      <Card>
        <CardHeader className="gap-3">
          <CardTitle as="h2" className="text-base">
            Résumé
          </CardTitle>
          <CardDescription>
            Les moyennes portent sur les journées journalisées, pas sur le calendrier.
          </CardDescription>
          <SelectField
            label="Période"
            options={PERIOD_OPTIONS}
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
          />
        </CardHeader>
        <CardContent>
          {report.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-40 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement du résumé…</span>
            </div>
          )}
          {report.error && (
            <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {describeError(report.error)}
            </p>
          )}
          {report.data && <Summary report={report.data} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Exporter
          </CardTitle>
          <CardDescription>
            Le CSV porte une ligne par journée journalisée ; une valeur inconnue y reste vide.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={download('csv')}
              disabled={exporter.isPending}
            >
              <Download aria-hidden="true" className="size-4" />
              CSV
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={download('pdf')}
              disabled={exporter.isPending}
            >
              <Download aria-hidden="true" className="size-4" />
              PDF
            </Button>
          </div>

          {exporter.isPending && (
            <p aria-live="polite" className="text-muted-foreground text-sm">
              Préparation du fichier…
            </p>
          )}
          {exporter.error && (
            <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {describeError(exporter.error)}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
