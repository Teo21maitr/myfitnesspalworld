import { TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { SelectField } from '@/components/form/select-field'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DEFAULT_NUTRIENT, NUTRIENT_OPTIONS } from '@/features/analysis/nutrient-options'
import { DEFAULT_PERIOD, PERIOD_OPTIONS, periodRange } from '@/features/analysis/period'
import { useNutrientAnalysis } from '@/features/analysis/use-analysis'
import type { AnalysisSource, NutrientAnalysis } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

function formatAmount(value: string | null): string {
  // « — » et non « 0 » : rien n'a été mesuré (spec 01 §8).
  if (value === null) return '—'
  return Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 1 })
}

function SourceRow({ source, total }: { source: AnalysisSource; total: string | null }) {
  const share = Number.isFinite(source.share) ? source.share : 0

  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate font-medium">{source.name}</span>
        <span className="text-muted-foreground shrink-0 text-sm tabular-nums">
          {formatAmount(source.total)}
          {total !== null && (
            <> · {share.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} %</>
          )}
        </span>
      </div>
      <div className="bg-muted h-2 overflow-hidden rounded-full">
        <div
          className="bg-primary h-full rounded-full"
          style={{ width: `${Math.min(100, Math.max(0, share))}%` }}
        />
      </div>
      <span className="text-muted-foreground text-xs">
        {source.entries} entrée{source.entries > 1 ? 's' : ''}
      </span>
    </li>
  )
}

function Result({ analysis }: { analysis: NutrientAnalysis }) {
  const sources = Array.isArray(analysis.sources) ? analysis.sources : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-2xl font-semibold tabular-nums">{formatAmount(analysis.total)}</span>
        <span className="text-muted-foreground text-sm">
          sur {analysis.logged_days} journée{analysis.logged_days > 1 ? 's' : ''} journalisée
          {analysis.logged_days > 1 ? 's' : ''}
        </span>
      </div>

      {analysis.is_partial && (
        <p className="text-muted-foreground flex items-start gap-2 rounded-md border p-3 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>
            {analysis.unknown_entries} entrée{analysis.unknown_entries > 1 ? 's' : ''} ne renseigne
            {analysis.unknown_entries > 1 ? 'nt' : ''} pas ce nutriment. Le total additionne ce qui
            est connu, et les parts affichées sont des minorants.
          </span>
        </p>
      )}

      {sources.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          Aucun aliment n’a apporté ce nutriment sur la période.
        </p>
      ) : (
        <ul aria-label="Principales sources" className="flex flex-col gap-4">
          {sources.map((source) => (
            <SourceRow key={source.name} source={source} total={analysis.total} />
          ))}
        </ul>
      )}
    </div>
  )
}

/** Food Analysis : d'où vient un nutriment sur une période (spec 01 §21). */
export function AnalysisPage() {
  const [nutrient, setNutrient] = useState(DEFAULT_NUTRIENT)
  const [period, setPeriod] = useState<string>(DEFAULT_PERIOD)

  const { from, to } = periodRange(period)
  const analysis = useNutrientAnalysis(nutrient, from, to)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analyse</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Les aliments qui ont le plus apporté un nutriment sur la période.
        </p>
      </div>

      <Card>
        <CardHeader className="gap-3">
          <CardTitle as="h2" className="text-base">
            Principales sources
          </CardTitle>
          <CardDescription>
            Les parts se calculent sur ce qui est renseigné : une entrée sans valeur n’est pas
            comptée pour zéro.
          </CardDescription>
          <div className="grid gap-3 sm:grid-cols-2">
            <SelectField
              label="Nutriment"
              options={NUTRIENT_OPTIONS}
              value={nutrient}
              onChange={(event) => setNutrient(event.target.value)}
            />
            <SelectField
              label="Période"
              options={PERIOD_OPTIONS}
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent>
          {analysis.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-40 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement de l’analyse…</span>
            </div>
          )}
          {analysis.error && (
            <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {describeError(analysis.error)}
            </p>
          )}
          {analysis.data && <Result analysis={analysis.data} />}
        </CardContent>
      </Card>
    </div>
  )
}
