import { Camera, CameraOff, Keyboard, Loader2, TriangleAlert } from 'lucide-react'
import { useCallback, useId, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBarcodeLookup } from '@/features/foods/use-foods'
import { useBarcodeScanner, type ScannerStatus } from '@/features/foods/use-barcode-scanner'
import { ApiError } from '@/lib/api/client'
import { describeError } from '@/lib/query-client'

/** Même règle que le backend : des chiffres, 8 à 24 positions. */
const BARCODE_PATTERN = /^\d{8,24}$/

/**
 * Messages d'indisponibilité de la caméra.
 *
 * Chacun doit dire quoi faire ensuite : la saisie manuelle reste toujours
 * possible, c'est elle qui rend l'écran utilisable en toute circonstance.
 */
const CAMERA_MESSAGES: Partial<Record<ScannerStatus, string>> = {
  denied:
    'L’accès à la caméra a été refusé. Autorisez-le dans les réglages de votre navigateur, ou saisissez le code à la main.',
  'no-camera': 'Aucune caméra n’a été trouvée sur cet appareil. Saisissez le code à la main.',
  unsupported: 'Ce navigateur ne permet pas d’ouvrir la caméra. Saisissez le code à la main.',
  error: 'Le scan n’a pas pu démarrer. Saisissez le code à la main.',
}

export function ScannerPage() {
  const navigate = useNavigate()
  const inputId = useId()
  const [manualCode, setManualCode] = useState('')
  const [notFoundCode, setNotFoundCode] = useState<string | null>(null)
  const lookup = useBarcodeLookup()

  const resolve = useCallback(
    (barcode: string) => {
      setNotFoundCode(null)
      lookup.mutate(barcode, {
        onSuccess: (food) => navigate(`/aliments/${food.id}`),
        onError: (error) => {
          if (error instanceof ApiError && error.code === 'product_not_found') {
            setNotFoundCode(barcode)
          }
        },
      })
    },
    [lookup, navigate],
  )

  const { videoRef, status, start, stop } = useBarcodeScanner({ onDetected: resolve })
  const cameraMessage = CAMERA_MESSAGES[status]
  const isManualValid = BARCODE_PATTERN.test(manualCode.trim())

  // Le produit est inconnu partout : on propose de le créer, code prérempli
  // (spec 01 §10).
  const creationLink = notFoundCode ? `/mes-aliments?creer=1&barcode=${notFoundCode}` : null

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Scanner un produit</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Visez le code-barres de l’emballage, ou saisissez-le vous-même.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Caméra</CardTitle>
          <CardDescription>
            {status === 'scanning'
              ? 'Recherche d’un code-barres…'
              : 'La caméra ne s’ouvre qu’à votre demande.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="bg-muted relative aspect-video overflow-hidden rounded-lg">
            <video
              ref={videoRef}
              className="size-full object-cover"
              muted
              playsInline
              aria-label="Aperçu de la caméra"
            />
            {status !== 'scanning' && (
              <div className="text-muted-foreground absolute inset-0 flex items-center justify-center">
                <CameraOff aria-hidden="true" className="size-8" />
              </div>
            )}
          </div>

          {cameraMessage && (
            <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {cameraMessage}
            </p>
          )}

          <div className="flex gap-2">
            {status === 'scanning' || status === 'starting' ? (
              <Button type="button" variant="outline" onClick={stop}>
                Arrêter le scan
              </Button>
            ) : (
              <Button type="button" onClick={() => void start()}>
                <Camera aria-hidden="true" className="size-4" />
                Démarrer le scan
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Saisie manuelle</CardTitle>
          <CardDescription>Le code se trouve sous les barres, sur l’emballage.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              if (isManualValid) {
                resolve(manualCode.trim())
              }
            }}
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={inputId}>Code-barres</Label>
              <div className="relative">
                <Keyboard
                  aria-hidden="true"
                  className="text-muted-foreground pointer-events-none absolute inset-y-0 left-3 my-auto size-4"
                />
                <Input
                  id={inputId}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="3017620422003"
                  className="pl-9"
                  value={manualCode}
                  onChange={(event) => setManualCode(event.target.value)}
                />
              </div>
              {manualCode.trim().length > 0 && !isManualValid && (
                <p className="text-muted-foreground text-xs">
                  Un code-barres comporte entre 8 et 24 chiffres.
                </p>
              )}
            </div>

            <Button type="submit" disabled={!isManualValid || lookup.isPending}>
              {lookup.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
              Chercher ce produit
            </Button>
          </form>
        </CardContent>
      </Card>

      {creationLink && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Produit inconnu</CardTitle>
            <CardDescription>
              Le code {notFoundCode} n’est ni dans vos aliments ni dans Open Food Facts.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to={creationLink}>Créer ce produit</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {lookup.isError && !notFoundCode && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(lookup.error)}
        </p>
      )}
    </div>
  )
}
