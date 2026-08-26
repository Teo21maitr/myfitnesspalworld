import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { describeError } from '@/lib/query-client'

import { DatePickerList } from './date-picker-list'

/**
 * Panneau de copie vers une ou plusieurs dates.
 *
 * Une carte dépliée plutôt qu'une modale : sur mobile, une modale de sélection
 * de dates est plus lourde qu'utile, et l'écran a la place.
 */
export function CopyDialog({
  title,
  description,
  isPending,
  error,
  onCopy,
  onClose,
}: {
  title: string
  description: string
  isPending: boolean
  error: unknown
  onCopy: (dates: string[]) => Promise<unknown>
  onClose: () => void
}) {
  const [dates, setDates] = useState<string[]>([])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (dates.length === 0) return

    void onCopy(dates).then(() => {
      toast.success(dates.length === 1 ? 'Copié vers 1 date.' : `Copié vers ${dates.length} dates.`)
      onClose()
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h3" className="text-base">
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DatePickerList dates={dates} onChange={setDates} />

          {error != null && (
            <p role="alert" className="text-destructive text-sm">
              {describeError(error)}
            </p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={isPending || dates.length === 0}>
              {isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
              Copier
            </Button>
            <Button type="button" variant="ghost" onClick={onClose}>
              Annuler
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
