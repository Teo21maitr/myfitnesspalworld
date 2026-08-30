import { Loader2, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Capture } from '@/features/camera/capture'
import { today } from '@/features/diary/dates'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { PhotoType } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import { MAX_PHOTOS, PHOTO_TYPES } from './photos'
import { useUploadPhotos } from './use-progress'

/**
 * Prise de vue puis relecture (spec 01 §20).
 *
 * L'angle se choisit **après** la prise, pas pendant : c'est en voyant ses
 * clichés côte à côte qu'on sait lequel est la face et lequel le profil.
 * `Capture` n'a donc pas à connaître cette notion, et reste la même pour les
 * trois écrans qui l'emploient.
 */
export function PhotoForm() {
  const [shots, setShots] = useState<{ file: File; url: string; type: PhotoType }[]>([])
  const [date, setDate] = useState(today())
  const [notes, setNotes] = useState('')

  const upload = useUploadPhotos()

  const collect = (files: File[]) => {
    setShots(
      files.map((file) => ({ file, url: URL.createObjectURL(file), type: 'front' as PhotoType })),
    )
  }

  const discard = () => {
    // Les aperçus sont des objets du navigateur : les laisser vivrait jusqu'au
    // rechargement de la page.
    for (const shot of shots) URL.revokeObjectURL(shot.url)
    setShots([])
  }

  const save = () => {
    upload.mutate(
      {
        date,
        notes: notes.trim() || undefined,
        photos: shots.map((shot) => ({ file: shot.file, photo_type: shot.type })),
      },
      {
        onSuccess: () => {
          toast.success('Photos enregistrées.')
          discard()
          setNotes('')
        },
      },
    )
  }

  if (shots.length === 0) {
    return (
      <Capture
        onAnalyze={collect}
        pending={upload.isPending}
        subject="de progression"
        analyzeLabel="Continuer"
        maxImages={MAX_PHOTOS}
        facingMode="user"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Nommez chaque angle, puis enregistrez. Ces photos ne sont jamais partageables.
      </p>

      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {shots.map((shot, index) => (
          <li key={shot.url} className="flex flex-col gap-1.5">
            <img
              src={shot.url}
              alt={`Aperçu ${index + 1}`}
              className="aspect-3/4 w-full rounded-md object-cover"
            />
            <select
              aria-label={`Angle de la photo ${index + 1}`}
              className="border-input bg-background h-9 w-full rounded-md border px-2 text-sm"
              value={shot.type}
              onChange={(event) =>
                setShots((current) =>
                  current.map((item, position) =>
                    position === index ? { ...item, type: event.target.value as PhotoType } : item,
                  ),
                )
              }
            >
              {PHOTO_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </li>
        ))}
      </ul>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="photo-date">Date</Label>
          <Input
            id="photo-date"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="photo-notes">Note (facultative)</Label>
          <Input
            id="photo-notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Fin de cycle, matin à jeun…"
          />
        </div>
      </div>

      {upload.isError && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(upload.error)}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={save} disabled={upload.isPending}>
          {upload.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
          Enregistrer
        </Button>
        <Button type="button" variant="ghost" onClick={discard} disabled={upload.isPending}>
          Recommencer
        </Button>
      </div>
    </div>
  )
}
