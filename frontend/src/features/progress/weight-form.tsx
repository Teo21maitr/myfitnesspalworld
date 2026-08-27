import { Loader2 } from 'lucide-react'
import { useId, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import { describeError } from '@/lib/query-client'

import { useSaveWeight } from './use-progress'

/**
 * Saisie d'une pesée (spec 01 §19).
 *
 * Une seconde saisie sur une date déjà pesée **modifie** la valeur. Le bouton
 * l'annonce avant l'envoi : découvrir après coup qu'une entrée a été
 * remplacée donnerait l'impression d'une donnée perdue.
 */
export function WeightForm({ measuredDates }: { measuredDates: Set<string> }) {
  const dateId = useId()
  const weightId = useId()
  const noteId = useId()

  const [date, setDate] = useState(today())
  const [weight, setWeight] = useState('')
  const [note, setNote] = useState('')

  const save = useSaveWeight()
  const isUpdate = measuredDates.has(date)
  const numeric = Number(weight.replace(',', '.'))
  const isValid = weight.trim() !== '' && Number.isFinite(numeric) && numeric > 0

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!isValid) return

    save.mutate(
      { date, weight_kg: String(numeric), notes: note.trim() || null },
      {
        onSuccess: () => {
          toast.success(isUpdate ? 'Pesée mise à jour.' : 'Pesée enregistrée.')
          setWeight('')
          setNote('')
        },
      },
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={dateId}>Date</Label>
          <Input
            id={dateId}
            type="date"
            value={date}
            max={today()}
            onChange={(event) => setDate(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor={weightId}>Poids (kg)</Label>
          <Input
            id={weightId}
            inputMode="decimal"
            placeholder="78,2"
            value={weight}
            onChange={(event) => setWeight(event.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={noteId}>Note (facultatif)</Label>
        <Input id={noteId} value={note} onChange={(event) => setNote(event.target.value)} />
      </div>

      {isUpdate && (
        <p className="text-muted-foreground text-xs">
          Cette date porte déjà une pesée : elle sera remplacée.
        </p>
      )}

      {save.isError && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(save.error)}
        </p>
      )}

      <Button type="submit" className="self-start" disabled={save.isPending || !isValid}>
        {save.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        {isUpdate ? 'Mettre à jour' : 'Enregistrer'}
      </Button>
    </form>
  )
}
