import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Lecture de code-barres par la caméra (spec 01 §10).
 *
 * Deux implémentations coexistent, faute d'une seule qui marche partout :
 *
 * - `BarcodeDetector`, natif, quand le navigateur le propose. Aucun octet
 *   téléchargé, décodage délégué au système ;
 * - ZXing sinon, importé dynamiquement. Il pèse plusieurs centaines de
 *   kilo-octets : il ne doit jamais entrer dans le bundle principal, d'où
 *   l'import différé au moment où le scan démarre réellement.
 *
 * Safari et Firefox n'implémentent pas `BarcodeDetector` ; sur iPhone, le
 * repli est donc le cas normal, pas l'exception.
 *
 * La saisie manuelle du code reste offerte en parallèle : un geste ne doit
 * jamais être l'unique moyen d'agir (spec 06 §6).
 */

/** Formats attendus sur un produit alimentaire emballé. */
const BARCODE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'itf'] as const

export type ScannerStatus =
  'idle' | 'starting' | 'scanning' | 'unsupported' | 'denied' | 'no-camera' | 'error'

interface BarcodeDetectorLike {
  detect: (source: CanvasImageSource) => Promise<{ rawValue: string }[]>
}

interface BarcodeDetectorConstructor {
  new (options?: { formats?: readonly string[] }): BarcodeDetectorLike
  getSupportedFormats?: () => Promise<string[]>
}

function nativeDetector(): BarcodeDetectorConstructor | null {
  const candidate = (globalThis as { BarcodeDetector?: BarcodeDetectorConstructor }).BarcodeDetector
  return typeof candidate === 'function' ? candidate : null
}

/** `true` si le navigateur peut ouvrir une caméra. */
export function supportsCamera(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
}

interface UseBarcodeScannerOptions {
  /** Appelé une seule fois, au premier code lu. */
  onDetected: (barcode: string) => void
}

export function useBarcodeScanner({ onDetected }: UseBarcodeScannerOptions) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const frameRef = useRef<number | null>(null)
  // Contrôleur du lecteur de secours : `stop()` doit pouvoir l'arrêter.
  const zxingControlsRef = useRef<{ stop: () => void } | null>(null)
  const stoppedRef = useRef(false)
  // Le rappel est gardé dans une ref : la boucle de détection ne doit pas se
  // reconstruire à chaque rendu du composant.
  const onDetectedRef = useRef(onDetected)
  const [status, setStatus] = useState<ScannerStatus>('idle')

  useEffect(() => {
    onDetectedRef.current = onDetected
  }, [onDetected])

  const stop = useCallback(() => {
    stoppedRef.current = true
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
    zxingControlsRef.current?.stop()
    zxingControlsRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setStatus('idle')
  }, [])

  const start = useCallback(async () => {
    if (!supportsCamera()) {
      setStatus('unsupported')
      return
    }

    stoppedRef.current = false
    setStatus('starting')

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        // Caméra arrière quand il y en a une : c'est celle qu'on pointe vers
        // l'emballage.
        video: { facingMode: 'environment' },
      })
    } catch (error) {
      setStatus(describeCameraFailure(error))
      return
    }

    // L'utilisateur a pu quitter la page pendant la demande d'autorisation.
    if (stoppedRef.current) {
      stream.getTracks().forEach((track) => track.stop())
      return
    }

    streamRef.current = stream
    const video = videoRef.current
    if (!video) {
      stream.getTracks().forEach((track) => track.stop())
      setStatus('error')
      return
    }

    video.srcObject = stream
    try {
      await video.play()
    } catch {
      // Certains navigateurs refusent la lecture automatique ; le flux reste
      // affiché et la détection peut démarrer malgré tout.
    }

    setStatus('scanning')

    const handle = (barcode: string) => {
      if (stoppedRef.current) return
      stoppedRef.current = true
      onDetectedRef.current(barcode)
    }

    const Native = nativeDetector()
    if (Native) {
      runNativeLoop(new Native({ formats: BARCODE_FORMATS }), video, stoppedRef, frameRef, handle)
      return
    }

    try {
      await runZxingLoop(video, stoppedRef, zxingControlsRef, handle)
    } catch {
      if (!stoppedRef.current) {
        setStatus('error')
      }
    }
  }, [])

  // Libère la caméra dès que la page est quittée : le voyant ne doit pas
  // rester allumé.
  useEffect(() => stop, [stop])

  return { videoRef, status, start, stop, usesNativeDetector: nativeDetector() !== null }
}

function describeCameraFailure(error: unknown): ScannerStatus {
  const name = (error as { name?: string } | null)?.name
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'denied'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'no-camera'
  return 'error'
}

function runNativeLoop(
  detector: BarcodeDetectorLike,
  video: HTMLVideoElement,
  stoppedRef: { current: boolean },
  frameRef: { current: number | null },
  onFound: (barcode: string) => void,
): void {
  const tick = async () => {
    if (stoppedRef.current) return

    try {
      const results = await detector.detect(video)
      const value = results[0]?.rawValue
      if (value) {
        onFound(value)
        return
      }
    } catch {
      // Une image illisible n'est pas une erreur : on réessaie à la suivante.
    }

    frameRef.current = requestAnimationFrame(() => void tick())
  }

  frameRef.current = requestAnimationFrame(() => void tick())
}

async function runZxingLoop(
  video: HTMLVideoElement,
  stoppedRef: { current: boolean },
  controlsRef: { current: { stop: () => void } | null },
  onFound: (barcode: string) => void,
): Promise<void> {
  // Import différé : c'est ce qui garde ZXing hors du bundle principal.
  const { BrowserMultiFormatReader } = await import('@zxing/browser')
  if (stoppedRef.current) return

  const reader = new BrowserMultiFormatReader()
  // Le rappel peut se déclencher avant que la promesse ne soit résolue : la
  // référence sert d'intermédiaire pour ne pas lire `controls` trop tôt.
  const controls = await reader.decodeFromVideoElement(video, (result) => {
    if (!result || stoppedRef.current) return
    onFound(result.getText())
    controlsRef.current?.stop()
  })

  controlsRef.current = controls
  if (stoppedRef.current) {
    controls.stop()
  }
}
