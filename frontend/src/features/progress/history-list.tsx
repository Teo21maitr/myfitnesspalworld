import { Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { formatDate } from '@/features/diary/dates'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { BodyMeasurementEntry, WeightEntry } from '@/lib/api/types'

import { MEASUREMENT_FIELDS } from './measurements'
import { useDeleteMeasurement, useDeleteWeight } from './use-progress'

export function WeightHistory({ entries }: { entries: WeightEntry[] }) {
  const remove = useDeleteWeight()

  if (entries.length === 0) {
    return <p className="text-muted-foreground text-sm">Aucune pesée enregistrée pour l’instant.</p>
  }

  return (
    <ul className="flex flex-col">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0"
        >
          <div className="flex min-w-0 flex-col">
            <span className="text-sm first-letter:uppercase">{formatDate(entry.date)}</span>
            {entry.notes && (
              <span className="text-muted-foreground truncate text-xs">{entry.notes}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              <NutrientValue value={entry.weight_kg} unit="kg" />
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Supprimer la pesée du ${formatDate(entry.date)}`}
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(entry.id, { onSuccess: () => toast.success('Pesée supprimée.') })
              }
            >
              <Trash2 aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function MeasurementHistory({ entries }: { entries: BodyMeasurementEntry[] }) {
  const remove = useDeleteMeasurement()

  if (entries.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Aucune mensuration enregistrée pour l’instant.
      </p>
    )
  }

  return (
    <ul className="flex flex-col">
      {entries.map((entry) => (
        <li key={entry.id} className="flex flex-col gap-1 border-b py-2 last:border-b-0">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm first-letter:uppercase">{formatDate(entry.date)}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Supprimer les mensurations du ${formatDate(entry.date)}`}
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(entry.id, {
                  onSuccess: () => toast.success('Mensurations supprimées.'),
                })
              }
            >
              <Trash2 aria-hidden="true" className="size-4" />
            </Button>
          </div>
          <dl className="flex flex-wrap gap-x-4 gap-y-1">
            {MEASUREMENT_FIELDS.filter((field) => entry[field.key] !== null).map((field) => (
              <div key={field.key} className="flex items-baseline gap-1">
                <dt className="text-muted-foreground text-xs">{field.label}</dt>
                <dd className="text-xs font-medium">
                  <NutrientValue value={entry[field.key]} unit={field.unit} />
                </dd>
              </div>
            ))}
          </dl>
        </li>
      ))}
    </ul>
  )
}
