import { Camera, CameraOff, Image as ImageIcon, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { captureFrame, prepareImage } from './image'
import { useCameraStream, type CameraStatus } from './use-camera-stream'

/** Aligné sur la limite du backend (spec 05 §14). */
export const MAX_IMAGES = 3

/**
 * Ce que dit l'application quand la caméra n'est pas disponible.
 *
 * Les états viennent du module caméra, partagés avec le lecteur de
 * codes-barres ; les messages, eux, ne le sont pas : chacun doit dire quoi
 * faire **ici**, et le repli n'est pas le même — un code se saisit à la main,
 * une assiette non.
 */
const CAMERA_MESSAGES: Partial<Record<CameraStatus, string>> = {
  denied:
    'L’accès à la caméra a été refusé. Autorisez-le dans les réglages de votre navigateur, ou importez une photo.',
  'no-camera': 'Aucune caméra n’a été trouvée sur cet appareil. Importez une photo.',
  unsupported: 'Ce navigateur ne permet pas d’ouvrir la caméra. Importez une photo.',
  error: 'La caméra n’a pas pu démarrer. Importez une photo.',
}

interface Photo {
  file: File
  /** URL d'aperçu, révoquée dès que la photo est retirée. */
  preview: string | null
}

function previewUrl(file: File): string | null {
  try {
    return URL.createObjectURL(file)
  } catch {
    // Environnement sans `createObjectURL` : la photo reste envoyable, seule
    // la vignette manque.
    return null
  }
}

function release(preview: string | null): void {
  if (preview === null) return
  try {
    URL.revokeObjectURL(preview)
  } catch {
    // Rien à faire : l'URL sera libérée avec le document.
  }
}

/**
 * Prise de vue.
 *
 * Partagée par le scan de repas et la lecture d'étiquette : le geste est le
 * même, seul le sujet change. La caméra s'ouvre dans la page — c'est ce qu'on
 * attend quand on a l'objet devant soi. L'import d'un fichier reste offert **en permanence**, et
 * pas seulement en repli : un geste ne doit jamais être l'unique moyen d'agir
 * (spec 06 §6). Il redevient le seul chemin quand la caméra est refusée,
 * absente ou non supportée.
 *
 * Le flux est relâché sur chaque sortie : démontage, fermeture explicite, et
 * démarrage de l'analyse. Personne ne filme son assiette pendant qu'on la lui
 * décrit.
 */
export function Capture({
  onAnalyze,
  pending,
  subject,
  analyzeLabel = 'Analyser',
}: {
  onAnalyze: (images: File[]) => void
  pending: boolean
  /** Complément du nom, au génitif : « du repas », « de l'étiquette ». */
  subject: string
  analyzeLabel?: string
}) {
  // Déstructuré plutôt que gardé en objet : `status` est une valeur de rendu,
  // et la lire à travers un objet qui porte aussi des références brouille la
  // distinction.
  const { videoRef, status: cameraStatus, start: startCamera, stop: stopCamera } = useCameraStream()
  const inputRef = useRef<HTMLInputElement>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [preparing, setPreparing] = useState(false)
  const [shooting, setShooting] = useState(false)

  // Les URL d'aperçu vivent aussi dans une référence, pour être libérées au
  // démontage : la page peut être quittée sans confirmer. Elle n'est écrite que
  // depuis les gestionnaires d'événements, jamais pendant le rendu.
  const previewsRef = useRef<string[]>([])
  useEffect(() => () => previewsRef.current.forEach(release), [])

  const apply = (next: Photo[]) => {
    previewsRef.current = next.map((photo) => photo.preview).filter((url) => url !== null)
    setPhotos(next)
  }

  const full = photos.length >= MAX_IMAGES
  const live = cameraStatus === 'active' || cameraStatus === 'starting'
  const cameraMessage = CAMERA_MESSAGES[cameraStatus]

  const closeCamera = () => stopCamera()

  const shoot = async () => {
    const video = videoRef.current
    if (!video) return

    setShooting(true)
    try {
      const file = await captureFrame(video)
      if (!file) return

      const next = [...photos, { file, preview: previewUrl(file) }]
      apply(next)
      // Trois photos suffisent : on rend la caméra plutôt que de la laisser
      // tourner sur un déclencheur devenu inerte.
      if (next.length >= MAX_IMAGES) closeCamera()
    } finally {
      setShooting(false)
    }
  }

  const addFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return

    setPreparing(true)
    try {
      const room = MAX_IMAGES - photos.length
      const prepared = await Promise.all(Array.from(files).slice(0, room).map(prepareImage))
      apply([...photos, ...prepared.map((file) => ({ file, preview: previewUrl(file) }))])
    } finally {
      setPreparing(false)
      // Permet de reprendre deux fois la même photo.
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const removeAt = (index: number) => {
    release(photos[index]?.preview ?? null)
    apply(photos.filter((_, position) => position !== index))
  }

  const analyze = () => {
    // Sortie n° 2 : l'analyse commence, la caméra n'a plus rien à filmer.
    closeCamera()
    onAnalyze(photos.map((photo) => photo.file))
  }

  return (
    <div className="space-y-4">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        className="sr-only"
        aria-label={`Importer une photo ${subject}`}
        onChange={(event) => void addFiles(event.target.files)}
      />

      {/* Toujours monté : `start()` a besoin de l'élément pour y attacher le
          flux, et il n'existerait pas encore s'il n'apparaissait qu'ensuite. */}
      <div className={cn('overflow-hidden rounded-xl border', !live && 'hidden')}>
        <video
          ref={videoRef}
          playsInline
          muted
          aria-label="Aperçu de la caméra"
          className="aspect-[4/3] w-full bg-black object-cover"
        />
      </div>

      {cameraMessage && (
        <p className="text-muted-foreground flex gap-2 text-sm">
          <CameraOff aria-hidden="true" className="size-4 shrink-0" />
          {cameraMessage}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {live ? (
          <>
            <Button
              type="button"
              className="flex-1"
              disabled={cameraStatus !== 'active' || shooting || full}
              onClick={() => void shoot()}
            >
              {shooting ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Camera aria-hidden="true" className="size-4" />
              )}
              Prendre la photo
            </Button>
            <Button type="button" variant="ghost" onClick={closeCamera}>
              Fermer la caméra
            </Button>
          </>
        ) : (
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            disabled={full || pending}
            onClick={() => void startCamera()}
          >
            <Camera aria-hidden="true" className="size-4" />
            Ouvrir la caméra
          </Button>
        )}

        <Button
          type="button"
          variant="outline"
          disabled={full || preparing || pending}
          onClick={() => inputRef.current?.click()}
        >
          {preparing ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <ImageIcon aria-hidden="true" className="size-4" />
          )}
          Importer
        </Button>
      </div>

      {full && (
        <p className="text-muted-foreground text-xs">
          {MAX_IMAGES} photos au maximum : au-delà, l&apos;analyse ne gagne rien.
        </p>
      )}

      {photos.length > 0 && (
        <ul className="grid grid-cols-3 gap-2">
          {photos.map((photo, index) => (
            <li key={`${photo.file.name}-${index}`} className="relative">
              {photo.preview ? (
                <img
                  src={photo.preview}
                  alt={`Photo ${index + 1}`}
                  className="aspect-square w-full rounded-lg object-cover"
                />
              ) : (
                <div className="bg-muted flex aspect-square w-full items-center justify-center rounded-lg text-xs">
                  Photo {index + 1}
                </div>
              )}
              <Button
                type="button"
                variant="secondary"
                size="icon"
                className="absolute top-1 right-1 size-7"
                aria-label={`Retirer la photo ${index + 1}`}
                onClick={() => removeAt(index)}
              >
                <Trash2 aria-hidden="true" className="size-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Button
        type="button"
        className="w-full"
        disabled={photos.length === 0 || pending || preparing}
        onClick={analyze}
      >
        {pending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        {analyzeLabel}
      </Button>
    </div>
  )
}
