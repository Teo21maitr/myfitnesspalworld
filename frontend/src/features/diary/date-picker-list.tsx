import { Plus, X } from 'lucide-react'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { shift, today } from './dates'

/**
 * Choix d'une ou plusieurs dates de destination.
 *
 * Quatre actions en ont besoin — dupliquer, copier un repas, copier une
 * journée, ajouter un aliment sur plusieurs dates. Un seul composant plutôt
 * que quatre variantes qui divergeraient.
 */
export function DatePickerList({
  dates,
  onChange,
  label = 'Dates de destination',
}: {
  dates: string[]
  onChange: (dates: string[]) => void
  label?: string
}) {
  const inputId = useId()
  const [draft, setDraft] = useState(() => shift(today(), 1))

  const add = () => {
    if (!draft || dates.includes(draft)) return
    onChange([...dates, draft].sort())
  }

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={inputId}>{label}</Label>

      <div className="flex gap-2">
        <Input
          id={inputId}
          type="date"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button type="button" variant="outline" onClick={add} disabled={!draft}>
          <Plus aria-hidden="true" className="size-4" />
          Ajouter
        </Button>
      </div>

      {dates.length === 0 ? (
        <p className="text-muted-foreground text-xs">Aucune date choisie.</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {dates.map((date) => (
            <li key={date}>
              <span className="bg-secondary flex items-center gap-1 rounded-full py-1 pl-3 pr-1 text-sm">
                {new Date(`${date}T12:00:00`).toLocaleDateString('fr-FR', {
                  day: 'numeric',
                  month: 'short',
                })}
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="size-6"
                  aria-label={`Retirer le ${date}`}
                  onClick={() => onChange(dates.filter((value) => value !== date))}
                >
                  <X aria-hidden="true" className="size-3" />
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
