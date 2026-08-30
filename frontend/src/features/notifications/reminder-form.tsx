import { TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { Reminder, ReminderType } from '@/lib/api/types'
import { cn } from '@/lib/utils'
import { describeError } from '@/lib/query-client'

import { useDeleteReminder, useSaveReminder } from './use-notifications'

/** Convention Python : 0 pour lundi, comme les surcharges d'objectifs. */
const DAYS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

/** Nom complet pour le lecteur d'écran : « L » et « M » ne s'entendent pas. */
const DAY_NAMES = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

const TYPES: { value: ReminderType; label: string; hint: string; time: string }[] = [
  { value: 'meal', label: 'Repas', hint: 'Journaliser ce qu’on a mangé', time: '12:30' },
  { value: 'weigh_in', label: 'Pesée', hint: 'Une par jour suffit', time: '08:00' },
  { value: 'plan', label: 'Planification', hint: 'Suivre le plan du jour', time: '09:00' },
]

function Editor({
  type,
  label,
  hint,
  existing,
  defaultTime,
}: {
  type: ReminderType
  label: string
  hint: string
  existing: Reminder | undefined
  defaultTime: string
}) {
  const save = useSaveReminder()
  const remove = useDeleteReminder()

  const [time, setTime] = useState(existing?.time.slice(0, 5) ?? defaultTime)
  const [days, setDays] = useState<number[]>(existing?.days_of_week ?? [0, 1, 2, 3, 4, 5, 6])

  const toggle = (day: number) =>
    setDays((current) =>
      current.includes(day) ? current.filter((value) => value !== day) : [...current, day].sort(),
    )

  return (
    <li
      aria-label={`Rappel ${label}`}
      className="flex flex-col gap-2 border-b py-3 last:border-b-0"
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-sm font-medium">{label}</span>
          <span className="text-muted-foreground text-xs">{hint}</span>
        </span>
        {existing && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-destructive"
            aria-label={`Supprimer le rappel ${label}`}
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(existing.id, { onSuccess: () => toast.success('Rappel supprimé.') })
            }
          >
            Retirer
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`time-${type}`}>Heure</Label>
          <Input
            id={`time-${type}`}
            type="time"
            className="w-32"
            value={time}
            onChange={(event) => setTime(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Jours</span>
          <div className="flex gap-1">
            {DAYS.map((initial, index) => (
              <button
                key={index}
                type="button"
                aria-pressed={days.includes(index)}
                aria-label={`${label} — ${DAY_NAMES[index]}`}
                onClick={() => toggle(index)}
                className={cn(
                  'size-9 rounded-md border text-sm',
                  days.includes(index)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'text-muted-foreground',
                )}
              >
                {initial}
              </button>
            ))}
          </div>
        </div>

        <Button
          type="button"
          aria-label={`${existing ? 'Mettre à jour' : 'Activer'} le rappel ${label}`}
          disabled={save.isPending || days.length === 0}
          onClick={() =>
            save.mutate(
              { reminder_type: type, time, days_of_week: days },
              { onSuccess: () => toast.success('Rappel enregistré.') },
            )
          }
        >
          {existing ? 'Mettre à jour' : 'Activer'}
        </Button>
      </div>

      {days.length === 0 && (
        <p className="text-muted-foreground text-xs">
          Choisissez au moins un jour, ou retirez le rappel.
        </p>
      )}

      {save.isError && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(save.error)}
        </p>
      )}
    </li>
  )
}

/**
 * Les trois rappels de la spec 01 §24, un par type.
 *
 * Un rappel se règle, il ne se crée pas deux fois : le backend met à jour
 * quand le type existe déjà.
 */
export function ReminderForm({ reminders }: { reminders: Reminder[] }) {
  return (
    <ul className="flex flex-col">
      {TYPES.map((entry) => (
        <Editor
          key={entry.value}
          type={entry.value}
          label={entry.label}
          hint={entry.hint}
          defaultTime={entry.time}
          existing={reminders.find((reminder) => reminder.reminder_type === entry.value)}
        />
      ))}
    </ul>
  )
}
