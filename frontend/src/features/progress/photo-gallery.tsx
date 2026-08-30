import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { formatDate } from '@/features/diary/dates'
import type { ProgressPhotoGroup } from '@/lib/api/types'

import { useDeletePhoto, useDeletePhotoGroup } from './use-progress'

/**
 * Une confirmation avant une suppression irréversible.
 *
 * Le fichier part avec la ligne (spec 01 §20) : l'écran doit le dire **avant**,
 * pas après. Un bouton qui détruit sans prévenir est un piège, pas un raccourci.
 */
function ConfirmDelete({
  label,
  pending,
  onConfirm,
}: {
  label: string
  pending: boolean
  onConfirm: () => void
}) {
  const [asking, setAsking] = useState(false)

  if (!asking) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="text-destructive"
        aria-label={`Supprimer ${label}`}
        onClick={() => setAsking(true)}
      >
        <Trash2 aria-hidden="true" className="size-4" />
      </Button>
    )
  }

  return (
    <span className="flex items-center gap-1">
      <span className="text-muted-foreground text-xs">Définitif ?</span>
      <Button
        type="button"
        variant="destructive-outline"
        size="sm"
        disabled={pending}
        onClick={onConfirm}
      >
        Supprimer
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => setAsking(false)}>
        Annuler
      </Button>
    </span>
  )
}

function GroupCard({ group }: { group: ProgressPhotoGroup }) {
  const removeGroup = useDeletePhotoGroup()
  const removePhoto = useDeletePhoto()

  const photos = Array.isArray(group.photos) ? group.photos : []

  return (
    <li className="flex flex-col gap-3 border-b py-4 last:border-b-0">
      <div className="flex items-start justify-between gap-4">
        <span className="flex flex-col">
          <span className="text-sm font-medium">{formatDate(group.date)}</span>
          <span className="text-muted-foreground text-xs">
            {photos.length} photo{photos.length > 1 ? 's' : ''}
            {group.weight_kg_snapshot && <> · {Number(group.weight_kg_snapshot)} kg</>}
            {group.notes && <> · {group.notes}</>}
          </span>
        </span>
        <ConfirmDelete
          label={`les photos du ${group.date}`}
          pending={removeGroup.isPending}
          onConfirm={() =>
            removeGroup.mutate(group.id, {
              onSuccess: () => toast.success('Photos supprimées.'),
            })
          }
        />
      </div>

      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {photos.map((photo) => (
          <li key={photo.id} className="flex flex-col gap-1">
            <img
              src={photo.url}
              alt={`${photo.photo_type_label} — ${group.date}`}
              loading="lazy"
              className="aspect-3/4 w-full rounded-md object-cover"
            />
            <span className="flex items-center justify-between gap-1">
              <span className="text-muted-foreground text-xs">{photo.photo_type_label}</span>
              <ConfirmDelete
                label={photo.photo_type_label}
                pending={removePhoto.isPending}
                onConfirm={() =>
                  removePhoto.mutate(
                    { groupId: group.id, photoId: photo.id },
                    { onSuccess: () => toast.success('Photo supprimée.') },
                  )
                }
              />
            </span>
          </li>
        ))}
      </ul>
    </li>
  )
}

export function PhotoGallery({ groups }: { groups: ProgressPhotoGroup[] }) {
  if (groups.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Aucune photo pour l’instant. La première sert de point de départ.
      </p>
    )
  }

  return (
    <ul aria-label="Photos de progression" className="flex flex-col">
      {groups.map((group) => (
        <GroupCard key={group.id} group={group} />
      ))}
    </ul>
  )
}
