import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCameraStream } from './use-camera-stream'

/**
 * Le piège de cet écran : **une caméra ne s'éteint pas toute seule**.
 *
 * Tant que les pistes ne sont pas arrêtées, le flux vit — voyant allumé,
 * batterie qui descend — et rien à l'écran ne le signale. Chaque sortie est
 * donc vérifiée en comptant les appels à `track.stop()`.
 */

function fakeStream() {
  const track = { stop: vi.fn(), kind: 'video' as const }
  return {
    track,
    stream: { getTracks: () => [track] } as unknown as MediaStream,
  }
}

/**
 * Installe `getUserMedia` et renvoie la piste rendue.
 *
 * `capture` reçoit de quoi débloquer l'autorisation plus tard : c'est ainsi
 * qu'on reproduit une autorisation accordée après le départ.
 */
function installCamera(capture?: (release: () => void) => void) {
  const { stream, track } = fakeStream()
  const getUserMedia = vi.fn(() =>
    capture
      ? new Promise<MediaStream>((resolve) => capture(() => resolve(stream)))
      : Promise.resolve(stream),
  )
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  return { track, getUserMedia, stream }
}

function attachVideo(ref: { current: HTMLVideoElement | null }) {
  const video = document.createElement('video')
  ref.current = video
  return video
}

beforeEach(() => {
  // jsdom n'implémente pas `play()` ; le hook absorbe déjà son échec, mais
  // autant ne pas polluer la sortie des tests.
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('la caméra est relâchée sur chaque sortie', () => {
  it('au démontage du composant', async () => {
    const { track } = installCamera()
    const { result, unmount } = renderHook(() => useCameraStream())
    attachVideo(result.current.videoRef)

    await act(async () => {
      await result.current.start()
    })
    expect(result.current.status).toBe('active')

    unmount()

    expect(track.stop).toHaveBeenCalledTimes(1)
  })

  it('à un arrêt demandé', async () => {
    const { track } = installCamera()
    const { result } = renderHook(() => useCameraStream())
    attachVideo(result.current.videoRef)

    await act(async () => {
      await result.current.start()
    })
    act(() => result.current.stop())

    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(result.current.status).toBe('idle')
  })

  it('quand l’autorisation arrive après le départ', async () => {
    // Le cas le plus facile à manquer : `getUserMedia` résout sur un composant
    // démonté, et le flux qu'elle rend n'a plus personne pour l'arrêter.
    let autoriser: (() => void) | undefined
    const { track } = installCamera((release) => {
      autoriser = release
    })

    const { result, unmount } = renderHook(() => useCameraStream())
    attachVideo(result.current.videoRef)

    let demarrage: Promise<unknown> | undefined
    act(() => {
      demarrage = result.current.start()
    })

    unmount()
    autoriser?.()
    await act(async () => {
      await demarrage
    })

    expect(track.stop).toHaveBeenCalledTimes(1)
  })

  it('quand aucun élément vidéo ne peut recevoir le flux', async () => {
    const { track } = installCamera()
    const { result } = renderHook(() => useCameraStream())
    // videoRef laissé vide : rien où attacher le flux.

    await act(async () => {
      await result.current.start()
    })

    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(result.current.status).toBe('error')
  })

  it('sans jamais arrêter deux fois la même piste', async () => {
    const { track } = installCamera()
    const { result, unmount } = renderHook(() => useCameraStream())
    attachVideo(result.current.videoRef)

    await act(async () => {
      await result.current.start()
    })
    act(() => result.current.stop())
    unmount()

    expect(track.stop).toHaveBeenCalledTimes(1)
  })
})

describe('les pannes portent un nom', () => {
  it.each([
    ['NotAllowedError', 'denied'],
    ['SecurityError', 'denied'],
    ['NotFoundError', 'no-camera'],
    ['OverconstrainedError', 'no-camera'],
    ['AbortError', 'error'],
  ])('%s donne l’état %s', async (name, attendu) => {
    const echec = Object.assign(new Error('refus'), { name })
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(echec) } })
    const { result } = renderHook(() => useCameraStream())
    attachVideo(result.current.videoRef)

    await act(async () => {
      await result.current.start()
    })

    await waitFor(() => expect(result.current.status).toBe(attendu))
  })

  it('un navigateur sans caméra est annoncé comme tel', async () => {
    vi.stubGlobal('navigator', {})
    const { result } = renderHook(() => useCameraStream())

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toBe('unsupported')
  })
})

describe('ce que start renvoie', () => {
  it('l’élément vidéo quand tout va bien', async () => {
    installCamera()
    const { result } = renderHook(() => useCameraStream())
    const video = attachVideo(result.current.videoRef)

    let rendu: HTMLVideoElement | null = null
    await act(async () => {
      rendu = await result.current.start()
    })

    expect(rendu).toBe(video)
  })

  it('null quand la caméra est refusée', async () => {
    const echec = Object.assign(new Error('refus'), { name: 'NotAllowedError' })
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(echec) } })
    const { result } = renderHook(() => useCameraStream())
    attachVideo(result.current.videoRef)

    let rendu: HTMLVideoElement | null = null
    await act(async () => {
      rendu = await result.current.start()
    })

    expect(rendu).toBeNull()
  })
})
