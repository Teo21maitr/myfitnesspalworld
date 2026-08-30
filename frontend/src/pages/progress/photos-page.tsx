import { TriangleAlert } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PhotoForm } from '@/features/progress/photo-form'
import { PhotoGallery } from '@/features/progress/photo-gallery'
import { usePhotoGroups } from '@/features/progress/use-progress'
import { describeError } from '@/lib/query-client'

/**
 * Photos de progression (spec 01 §20).
 *
 * Ce sont les seules données du projet qui vivent hors de la base. Elles ne
 * sont **jamais partageables**, sous aucune forme — et l'écran le dit, parce
 * qu'un utilisateur n'a pas à deviner ce que l'application fait de ses images.
 */
export function PhotosPage() {
  const groups = usePhotoGroups()
  const rows = Array.isArray(groups.data?.results) ? groups.data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Photos</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Elles ne sont jamais partageables et ne quittent jamais votre compte.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Ajouter
          </CardTitle>
          <CardDescription>
            Jusqu’à quatre angles pour une même date : face, profil, dos et autre.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PhotoForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Mes photos
          </CardTitle>
          <CardDescription>
            La suppression est définitive : le fichier part avec la ligne.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {groups.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-40 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement des photos…</span>
            </div>
          )}
          {groups.error && (
            <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {describeError(groups.error)}
            </p>
          )}
          {groups.data && <PhotoGallery groups={rows} />}
        </CardContent>
      </Card>
    </div>
  )
}
