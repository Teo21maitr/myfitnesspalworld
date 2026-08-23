import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, RefreshCw, TriangleAlert, WifiOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useOnlineStatus } from '@/hooks/use-online-status'
import { describeError } from '@/lib/query-client'
import { cn } from '@/lib/utils'

import { healthQueryKey } from './api'
import { useHealth } from './use-health'

function StatusRow({ label, value }: { label: string; value: string }) {
  const ok = value === 'ok'
  return (
    <div className="flex items-center justify-between border-b py-2 last:border-b-0">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span
        className={cn('text-sm font-medium', ok ? 'text-success' : 'text-destructive')}
        data-testid={`health-${label.toLowerCase()}`}
      >
        {ok ? 'OK' : 'Erreur'}
      </span>
    </div>
  )
}

/**
 * Carte de vérification du lien frontend ↔ backend.
 *
 * Elle couvre les états obligatoires d'une page de données : chargement,
 * erreur, hors ligne et succès (spec 06 §11).
 */
export function HealthCard() {
  const { data, error, isPending, isFetching } = useHealth()
  const isOnline = useOnlineStatus()
  const queryClient = useQueryClient()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connexion au backend</CardTitle>
        <CardDescription>
          Vérifie que l’API répond et que ses dépendances sont disponibles.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isOnline && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm">
            <WifiOff aria-hidden="true" className="size-4" />
            Hors connexion : impossible d’interroger le serveur.
          </p>
        )}

        {isPending && (
          <div aria-busy="true" className="flex flex-col gap-2">
            <div className="bg-muted h-4 w-40 animate-pulse rounded" />
            <div className="bg-muted h-4 w-28 animate-pulse rounded" />
            <span className="sr-only">Chargement du statut…</span>
          </div>
        )}

        {error && (
          <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
            <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {describeError(error)}
          </p>
        )}

        {data && (
          <div className="flex flex-col gap-1">
            <p
              className={cn(
                'flex items-center gap-2 text-sm font-medium',
                data.status === 'ok' ? 'text-success' : 'text-destructive',
              )}
            >
              {data.status === 'ok' ? (
                <CheckCircle2 aria-hidden="true" className="size-4" />
              ) : (
                <TriangleAlert aria-hidden="true" className="size-4" />
              )}
              {data.status === 'ok' ? 'API opérationnelle' : 'API dégradée'}
              <span className="text-muted-foreground font-normal">v{data.version}</span>
            </p>

            <div className="mt-2">
              <StatusRow label="Database" value={data.checks.database} />
              <StatusRow label="Cache" value={data.checks.cache} />
            </div>
          </div>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          disabled={isFetching}
          onClick={() => queryClient.invalidateQueries({ queryKey: healthQueryKey })}
        >
          <RefreshCw aria-hidden="true" className={cn(isFetching && 'animate-spin')} />
          Actualiser
        </Button>
      </CardContent>
    </Card>
  )
}
