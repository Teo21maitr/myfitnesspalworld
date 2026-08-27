import { Loader2, Share2 } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { useFriends } from '@/features/friends/use-friends'
import type { ShareResourceType } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import { useCreateShare } from './use-shares'

/**
 * Partage d'une ressource (spec 01 §18).
 *
 * Trois portées : garder pour soi, ouvrir à un ami nommément, ou à tous les
 * comptes actifs. Le partage ciblé suppose une amitié, faute de quoi le retrait
 * d'ami n'aurait rien à révoquer.
 */
export function ShareDialog({
  resourceType,
  resourceId,
  label,
  triggerText = 'Partager',
}: {
  resourceType: ShareResourceType
  resourceId?: number
  label: string
  /** Texte du bouton. À préciser quand plusieurs dialogues coexistent :
   *  deux boutons « Partager » côte à côte sont indiscernables à l'œil. */
  triggerText?: string
}) {
  const selectId = useId()
  const [open, setOpen] = useState(false)
  const [targetId, setTargetId] = useState('')

  const friends = useFriends()
  const create = useCreateShare()

  const friendRows = useMemo(
    () => (Array.isArray(friends.data?.results) ? friends.data.results : []),
    [friends.data],
  )

  const submit = (visibility: 'specific_user' | 'app_users') => {
    create.mutate(
      {
        resource_type: resourceType,
        resource_id: resourceId ?? null,
        visibility,
        target_user_id: visibility === 'specific_user' ? Number(targetId) : null,
      },
      {
        onSuccess: () => {
          toast.success('Partagé.')
          setOpen(false)
          setTargetId('')
        },
      },
    )
  }

  if (!open) {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={`Partager ${label}`}
        onClick={() => setOpen(true)}
      >
        <Share2 aria-hidden="true" className="size-4" />
        {triggerText}
      </Button>
    )
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle as="h3" className="text-base">
          Partager {label}
        </CardTitle>
        <CardDescription>
          Une ressource reçue se lit et se copie, jamais ne se modifie.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {friendRows.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Vous n’avez pas encore d’amis. Le partage à une personne précise en demande un.
          </p>
        ) : (
          <div className="flex items-end gap-2">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor={selectId}>Avec qui</Label>
              <select
                id={selectId}
                className="border-input bg-background h-11 w-full rounded-md border px-3 text-base"
                value={targetId}
                onChange={(event) => setTargetId(event.target.value)}
              >
                <option value="">Choisir…</option>
                {friendRows.map((friend) => (
                  <option key={friend.id} value={String(friend.id)}>
                    {friend.username}
                  </option>
                ))}
              </select>
            </div>
            <Button
              type="button"
              aria-label="Confirmer le partage"
              disabled={create.isPending || targetId === ''}
              onClick={() => submit('specific_user')}
            >
              {create.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
              Partager
            </Button>
          </div>
        )}

        {create.isError && (
          <p role="alert" className="text-destructive text-sm">
            {describeError(create.error)}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={create.isPending}
            onClick={() => submit('app_users')}
          >
            Ouvrir à tous les comptes actifs
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
            Annuler
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
