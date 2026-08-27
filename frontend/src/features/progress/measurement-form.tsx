import { Loader2 } from 'lucide-react'
import { useId, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import type { BodyMeasurementEntry } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import { MEASUREMENT_FIELDS, draftFrom, type MeasurementDraft } from './measurements'
import { useSaveMeasurement } from './use-progress'

/** Un champ vide reste inconnu : il part `null`, jamais 0 (spec 01 §8). */
function optional(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : String(Number(trimmed.replace(',', '.')))
}

/**
 * Saisie des mensurations d'une date (spec 01 §19).
 *
 * Le formulaire est prérempli avec les mesures déjà relevées ce jour-là : il
 * édite la journée entière, si bien qu'effacer un champ efface la mesure.
 * Sans ce préremplissage, enregistrer un tour de taille effacerait la masse
 * grasse saisie plus tôt.
 */
export function MeasurementForm({ entries }: { entries: BodyMeasurementEntry[] }) {
  const dateId = useId()
  const fieldId = useId()

  const [date, setDate] = useState(today())
  const existing = entries.find((entry) => entry.date === date)
  const save = useSaveMeasurement()

  // Le brouillon suit la date choisie et l'entrée qu'elle porte. La signature
  // inclut `updated_at` : un rechargement qui ne change rien laisse la saisie
  // en cours intacte, alors qu'un enregistrement la resynchronise.
  const signature = `${date}:${existing?.updated_at ?? ''}`
  const [draft, setDraft] = useState<MeasurementDraft>(() => draftFrom(existing))
  const [syncedWith, setSyncedWith] = useState(signature)

  if (syncedWith !== signature) {
    setSyncedWith(signature)
    setDraft(draftFrom(existing))
  }

  const hasValue = MEASUREMENT_FIELDS.some((field) => draft[field.key].trim() !== '')

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!hasValue) return

    save.mutate(
      {
        date,
        ...MEASUREMENT_FIELDS.reduce(
          (payload, field) => ({ ...payload, [field.key]: optional(draft[field.key]) }),
          {},
        ),
      },
      {
        onSuccess: () => {
          toast.success(existing ? 'Mensurations mises à jour.' : 'Mensurations enregistrées.')
        },
      },
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5 sm:max-w-xs">
        <Label htmlFor={dateId}>Date</Label>
        <Input
          id={dateId}
          type="date"
          value={date}
          max={today()}
          onChange={(event) => setDate(event.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {MEASUREMENT_FIELDS.map((field) => (
          <div key={field.key} className="flex flex-col gap-1.5">
            <Label htmlFor={`${fieldId}-${field.key}`}>
              {field.label} ({field.unit})
            </Label>
            <Input
              id={`${fieldId}-${field.key}`}
              inputMode="decimal"
              value={draft[field.key]}
              onChange={(event) =>
                setDraft((current) => ({ ...current, [field.key]: event.target.value }))
              }
            />
          </div>
        ))}
      </div>

      <p className="text-muted-foreground text-xs">
        Toutes les mesures sont facultatives. Un champ laissé vide reste inconnu et s’affichera « —
        » : il n’est pas ramené à zéro.
      </p>

      {save.isError && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(save.error)}
        </p>
      )}

      <Button type="submit" className="self-start" disabled={save.isPending || !hasValue}>
        {save.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        {existing ? 'Mettre à jour' : 'Enregistrer'}
      </Button>
    </form>
  )
}
