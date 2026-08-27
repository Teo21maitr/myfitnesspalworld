import { Camera, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'

import { prepareImage } from './image'

/** Aligné sur la limite du backend (spec 05 §14). */
export const MAX_IMAGES = 3

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
 * Un `<input type="file" capture>` plutôt qu'un flux vidéo : il n'y a rien à
 * viser en direct, et cet input ouvre l'appareil photo sur mobile comme le
 * sélecteur de fichiers sur desktop, sans permission caméra à demander ni
 * bibliothèque à charger.
 */
export function Capture({
  onAnalyze,
  pending,
}: {
  onAnalyze: (images: File[]) => void
  pending: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [preparing, setPreparing] = useState(false)

  // Les URL d'aperçu vivent aussi dans une référence, pour être libérées au
  // démontage : la page peut être quittée sans confirmer. Elle n'est écrite
  // que depuis les gestionnaires d'événements, jamais pendant le rendu.
  const previewsRef = useRef<string[]>([])
  useEffect(() => () => previewsRef.current.forEach(release), [])

  const apply = (next: Photo[]) => {
    previewsRef.current = next.map((photo) => photo.preview).filter((url) => url !== null)
    setPhotos(next)
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

  const full = photos.length >= MAX_IMAGES

  return (
    <div className="space-y-4">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        multiple
        className="sr-only"
        aria-label="Photo du repas"
        onChange={(event) => void addFiles(event.target.files)}
      />

      <Button
        type="button"
        variant="outline"
        className="w-full"
        disabled={full || preparing || pending}
        onClick={() => inputRef.current?.click()}
      >
        {preparing ? (
          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
        ) : (
          <Camera aria-hidden="true" className="size-4" />
        )}
        {photos.length === 0 ? 'Prendre une photo' : 'Ajouter une photo'}
      </Button>

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
        onClick={() => onAnalyze(photos.map((photo) => photo.file))}
      >
        {pending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
        Analyser
      </Button>
    </div>
  )
}
