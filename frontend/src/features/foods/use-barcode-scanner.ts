import { useCallback, useEffect, useRef, useState } from 'react'

import { useCameraStream, type CameraStatus } from '@/features/camera/use-camera-stream'

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
 *
 * L'ouverture et la fermeture du flux vivent dans `useCameraStream`, partagées
 * avec la prise de vue d'un repas. Ce module ne garde que la détection.
 */

/** Formats attendus sur un produit alimentaire emballé. */
const BARCODE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'itf'] as const

export type ScannerStatus =
  'idle' | 'starting' | 'scanning' | 'unsupported' | 'denied' | 'no-camera' | 'error'

/** « Caméra ouverte » se dit « en train de scanner » ici, et rien d'autre ne change. */
function toScannerStatus(status: CameraStatus): ScannerStatus {
  return status === 'active' ? 'scanning' : status
}

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

interface UseBarcodeScannerOptions {
  /** Appelé une seule fois, au premier code lu. */
  onDetected: (barcode: string) => void
}

export function useBarcodeScanner({ onDetected }: UseBarcodeScannerOptions) {
  const camera = useCameraStream()
  const frameRef = useRef<number | null>(null)
  // Contrôleur du lecteur de secours : `stop()` doit pouvoir l'arrêter.
  const zxingControlsRef = useRef<{ stop: () => void } | null>(null)
  // Le rappel est gardé dans une ref : la boucle de détection ne doit pas se
  // reconstruire à chaque rendu du composant.
  const onDetectedRef = useRef(onDetected)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    onDetectedRef.current = onDetected
  }, [onDetected])

  const { start: startCamera, stop: stopCamera, stoppedRef } = camera

  const stop = useCallback(() => {
    // Avant tout : la détection en vol doit renoncer plutôt que de rappeler
    // l'appelant sur un écran qu'il vient de quitter.
    stoppedRef.current = true
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
    zxingControlsRef.current?.stop()
    zxingControlsRef.current = null
    setFailed(false)
    stopCamera()
  }, [stopCamera, stoppedRef])

  const start = useCallback(async () => {
    setFailed(false)
    const video = await startCamera()
    if (!video) return

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
        setFailed(true)
      }
    }
  }, [startCamera, stoppedRef])

  return {
    videoRef: camera.videoRef,
    status: failed ? ('error' as ScannerStatus) : toScannerStatus(camera.status),
    start,
    stop,
    usesNativeDetector: nativeDetector() !== null,
  }
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
