import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Cycle de vie d'un flux caméra.
 *
 * Extrait du lecteur de codes-barres, qui n'en était pas le seul usage : la
 * prise de vue d'un repas ouvre la même caméra, avec les mêmes autorisations à
 * demander et les mêmes pannes à nommer.
 *
 * **Un flux ne s'arrête pas parce qu'on a changé d'écran.** Tant que ses pistes
 * ne sont pas explicitement arrêtées, la caméra reste allumée — voyant compris,
 * batterie comprise — sans que rien à l'écran ne le laisse deviner. Quatre
 * sorties doivent donc l'éteindre :
 *
 * 1. le démontage du composant ;
 * 2. un arrêt demandé par l'appelant ;
 * 3. un échec après ouverture — pas de `<video>` où l'attacher ;
 * 4. **une autorisation accordée après le départ** : `getUserMedia` résout sur
 *    un composant démonté, et le flux qu'elle rend n'a plus personne pour
 *    l'arrêter. C'est la raison d'être de `stoppedRef`.
 */

export type CameraStatus =
  'idle' | 'starting' | 'active' | 'unsupported' | 'denied' | 'no-camera' | 'error'

/** `true` si le navigateur peut ouvrir une caméra. */
export function supportsCamera(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
}

/** Traduit l'échec de `getUserMedia` en état nommé, pour un message utile. */
export function describeCameraFailure(error: unknown): CameraStatus {
  const name = (error as { name?: string } | null)?.name
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'denied'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'no-camera'
  return 'error'
}

export function useCameraStream() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const stoppedRef = useRef(false)
  const [status, setStatus] = useState<CameraStatus>('idle')

  const stop = useCallback(() => {
    stoppedRef.current = true
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setStatus('idle')
  }, [])

  /** Ouvre la caméra. Résout avec l'élément vidéo prêt, ou `null` si l'ouverture a échoué. */
  const start = useCallback(async (): Promise<HTMLVideoElement | null> => {
    if (!supportsCamera()) {
      setStatus('unsupported')
      return null
    }

    stoppedRef.current = false
    setStatus('starting')

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        // Caméra arrière quand il y en a une : c'est celle qu'on pointe vers
        // l'emballage ou vers l'assiette.
        video: { facingMode: 'environment' },
      })
    } catch (error) {
      setStatus(describeCameraFailure(error))
      return null
    }

    // Sortie n° 4 : l'utilisateur a quitté pendant la demande d'autorisation.
    if (stoppedRef.current) {
      stream.getTracks().forEach((track) => track.stop())
      return null
    }

    streamRef.current = stream
    const video = videoRef.current
    if (!video) {
      stream.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      setStatus('error')
      return null
    }

    video.srcObject = stream
    try {
      await video.play()
    } catch {
      // Certains navigateurs refusent la lecture automatique ; le flux reste
      // affiché et l'usage peut continuer.
    }

    setStatus('active')
    return video
  }, [])

  // Libère la caméra dès que la page est quittée : le voyant ne doit pas rester
  // allumé.
  useEffect(() => stop, [stop])

  return { videoRef, status, setStatus, start, stop, stoppedRef }
}
