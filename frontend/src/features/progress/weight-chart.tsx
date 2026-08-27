import type { ChartSeries } from '@/lib/api/types'

/**
 * Courbe d'une métrique de progression (spec 01 §19).
 *
 * L'axe des abscisses est **temporel** : un point par mesure, placé selon sa
 * date réelle. Un espacement régulier ferait paraître identiques deux jours
 * et trois semaines, et un trou de vacances ressemblerait à une progression
 * régulière.
 *
 * Les libellés restent en HTML plutôt qu'en `<text>` : le SVG est réduit de
 * 640 à environ 343 px sur mobile, ce qui ramènerait une police de 11 px à
 * 6 px.
 */

const WIDTH = 640
const HEIGHT = 220
const PADDING = { top: 12, right: 12, bottom: 12, left: 12 }
const INNER_WIDTH = WIDTH - PADDING.left - PADDING.right
const INNER_HEIGHT = HEIGHT - PADDING.top - PADDING.bottom

const MILLISECONDS_PER_DAY = 86_400_000

function daysBetween(from: string, to: string): number {
  return Math.round(
    (Date.parse(`${to}T12:00:00`) - Date.parse(`${from}T12:00:00`)) / MILLISECONDS_PER_DAY,
  )
}

function formatShort(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
  })
}

function formatNumber(value: number, maximumFractionDigits = 1): string {
  return value.toLocaleString('fr-FR', { maximumFractionDigits })
}

export function ProgressChart({ series, label }: { series: ChartSeries; label: string }) {
  const points = Array.isArray(series.points) ? series.points : []

  if (points.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Aucune mesure sur cette période. La courbe apparaîtra dès la deuxième saisie.
      </p>
    )
  }

  const first = points[0]!.date
  const last = points[points.length - 1]!.date
  const span = daysBetween(first, last)

  const target = series.target === null ? null : Number(series.target)
  const values = points.flatMap((point) => [Number(point.value), Number(point.moving_average)])
  if (target !== null) values.push(target)

  let low = Math.min(...values)
  let high = Math.max(...values)
  if (low === high) {
    // Une mesure unique, ou plusieurs identiques : sans marge, la ligne
    // sortirait du cadre par division par zéro.
    low -= 1
    high += 1
  }

  // Un seul jour couvert : le point est centré plutôt que collé à gauche.
  const x = (date: string) =>
    span === 0
      ? PADDING.left + INNER_WIDTH / 2
      : PADDING.left + (daysBetween(first, date) / span) * INNER_WIDTH

  const y = (value: number) => PADDING.top + (1 - (value - low) / (high - low)) * INNER_HEIGHT

  const polyline = (pick: (point: (typeof points)[number]) => string) =>
    points.map((point) => `${x(point.date)},${y(Number(pick(point)))}`).join(' ')

  const measured = points.map((point) => Number(point.value))
  const lowestMeasure = Math.min(...measured)
  const highestMeasure = Math.max(...measured)

  const trend = series.trend_per_week === null ? null : Number(series.trend_per_week)
  const caption =
    `${label} du ${formatShort(first)} au ${formatShort(last)}, ` +
    `${points.length} mesure${points.length > 1 ? 's' : ''}, ` +
    `de ${formatNumber(lowestMeasure)} à ${formatNumber(highestMeasure)} ${series.unit}.`

  return (
    <figure className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full"
        role="img"
        aria-label={caption}
      >
        {target !== null && target >= low && target <= high && (
          <line
            x1={PADDING.left}
            x2={WIDTH - PADDING.right}
            y1={y(target)}
            y2={y(target)}
            stroke="currentColor"
            strokeWidth={1}
            strokeDasharray="6 4"
            vectorEffect="non-scaling-stroke"
            className="text-muted-foreground/60"
          />
        )}

        {points.length > 1 && (
          <>
            <polyline
              points={polyline((point) => point.value)}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
              className="text-muted-foreground/70"
            />
            <polyline
              points={polyline((point) => point.moving_average)}
              fill="none"
              stroke="currentColor"
              strokeWidth={2.5}
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
              className="text-primary"
            />
          </>
        )}

        {points.map((point) => (
          <circle
            key={point.date}
            cx={x(point.date)}
            cy={y(Number(point.value))}
            r={3}
            fill="currentColor"
            className="text-muted-foreground"
          />
        ))}
      </svg>

      <div className="text-muted-foreground flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs">
        <span>{formatShort(first)}</span>
        {/* La plage décrit les mesures, non le domaine du tracé : celui-ci est
            étiré par la ligne d'objectif, qui n'est pas une mesure. */}
        <span>
          de {formatNumber(lowestMeasure)} à {formatNumber(highestMeasure)} {series.unit}
        </span>
        <span>{formatShort(last)}</span>
      </div>

      <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="bg-muted-foreground size-1.5 rounded-full" />
          Mesures
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="bg-primary h-0.5 w-4 rounded-full" />
          Moyenne 7 jours
        </span>
        {target !== null && (
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="border-muted-foreground/60 w-4 border-t border-dashed"
            />
            Objectif
          </span>
        )}
        {trend !== null && (
          <span>
            {/* Deux décimales : au dixième près, une tendance de −0,35 kg par
                semaine s'afficherait « −0,4 » et perdrait son sens. */}
            Tendance {trend > 0 ? '+' : trend < 0 ? '−' : ''}
            {formatNumber(Math.abs(trend), 2)} {series.unit} par semaine
          </span>
        )}
      </div>

      {/* Une courbe sans équivalent textuel n'est pas lisible au lecteur
          d'écran (spec 06 §12). */}
      <figcaption className="sr-only">
        <table>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Mesure</th>
              <th scope="col">Moyenne 7 jours</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.date}>
                <td>{formatShort(point.date)}</td>
                <td>
                  {formatNumber(Number(point.value))} {series.unit}
                </td>
                <td>
                  {formatNumber(Number(point.moving_average))} {series.unit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </figcaption>
    </figure>
  )
}
