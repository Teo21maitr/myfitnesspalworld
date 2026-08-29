import { Trash2, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ShareDialog } from '@/features/shares/share-dialog'
import { useReceivedShares, useRevokeShare, useShares } from '@/features/shares/use-shares'
import type { SharePermission } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

const RESOURCE_LABELS: Record<string, string> = {
  food: 'Aliment',
  recipe: 'Recette',
  saved_meal: 'Repas enregistré',
  shopping_list: 'Liste de courses',
  diary: 'Journal',
  progress: 'Progression',
}

/** Lien vers ce qu'on a reçu, quand il en existe un. */
function receivedLink(share: SharePermission): { to: string; label: string } | null {
  if (share.resource_type === 'recipe' && share.resource_id !== null) {
    return { to: `/recettes/${share.resource_id}`, label: 'Ouvrir' }
  }
  if (share.resource_type === 'food' && share.resource_id !== null) {
    return { to: `/aliments/${share.resource_id}`, label: 'Ouvrir' }
  }
  if (share.resource_type === 'diary') {
    return { to: `/amis/${share.owner.id}/journal`, label: 'Son journal' }
  }
  if (share.resource_type === 'saved_meal') {
    return { to: '/mes-repas', label: 'Ouvrir' }
  }
  if (share.resource_type === 'shopping_list' && share.resource_id !== null) {
    return { to: `/courses/${share.resource_id}`, label: 'Ouvrir' }
  }
  if (share.resource_type === 'progress') {
    return { to: `/amis/${share.owner.id}/progression`, label: 'Sa progression' }
  }
  return null
}

function ErrorLine({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {describeError(error)}
    </p>
  )
}

function GrantedRow({ share }: { share: SharePermission }) {
  const revoke = useRevokeShare()

  return (
    <li className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0">
      <span className="flex flex-col">
        <span className="text-sm font-medium">{share.resource_name}</span>
        <span className="text-muted-foreground text-xs">
          {RESOURCE_LABELS[share.resource_type] ?? share.resource_type} ·{' '}
          {share.target_user ? share.target_user.username : 'tous les comptes actifs'}
        </span>
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Révoquer le partage de ${share.resource_name}`}
        disabled={revoke.isPending}
        onClick={() =>
          revoke.mutate(share.id, { onSuccess: () => toast.success('Partage révoqué.') })
        }
      >
        <Trash2 aria-hidden="true" className="size-4" />
      </Button>
    </li>
  )
}

/** Ce que je partage et ce qu'on m'a partagé (spec 01 §18). */
export function SharesPage() {
  const granted = useShares()
  const received = useReceivedShares()

  const grantedRows = Array.isArray(granted.data?.results) ? granted.data.results : []
  const receivedRows = Array.isArray(received.data?.results) ? received.data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Partages</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Tout est privé par défaut. Un partage se révoque à tout moment.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Partager mon suivi
          </CardTitle>
          <CardDescription>
            Le journal et la progression se partagent séparément : ouvrir l’un n’ouvre pas l’autre.
            Les photos de progression ne sont jamais partagées.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <ShareDialog resourceType="diary" label="mon journal" triggerText="Mon journal" />
          <ShareDialog
            resourceType="progress"
            label="ma progression"
            triggerText="Ma progression"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Ce que je partage
          </CardTitle>
          {grantedRows.length === 0 && !granted.isPending && (
            <CardDescription>
              Rien pour l’instant. Le bouton « Partager » se trouve sur chaque recette, chaque
              aliment personnel, chaque repas enregistré et chaque liste de courses.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          {granted.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-16 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement des partages…</span>
            </div>
          )}
          {granted.error && <ErrorLine error={granted.error} />}
          {grantedRows.length > 0 && (
            <ul className="flex flex-col">
              {grantedRows.map((share) => (
                <GrantedRow key={share.id} share={share} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Ce qu’on m’a partagé
          </CardTitle>
          {receivedRows.length === 0 && !received.isPending && (
            <CardDescription>Rien pour l’instant.</CardDescription>
          )}
        </CardHeader>
        <CardContent>
          {received.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-16 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement des partages reçus…</span>
            </div>
          )}
          {received.error && <ErrorLine error={received.error} />}
          {receivedRows.length > 0 && (
            <ul className="flex flex-col">
              {receivedRows.map((share) => {
                const link = receivedLink(share)
                return (
                  <li
                    key={share.id}
                    className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0"
                  >
                    <span className="flex flex-col">
                      <span className="text-sm font-medium">{share.resource_name}</span>
                      <span className="text-muted-foreground text-xs">
                        {RESOURCE_LABELS[share.resource_type] ?? share.resource_type} · de{' '}
                        {share.owner.username}
                      </span>
                    </span>
                    {link && (
                      <Button asChild variant="outline" size="sm">
                        <Link to={link.to}>{link.label}</Link>
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
