import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Capture } from './capture'

/** Piste de caméra simulée, dont on compte les arrêts. */
function installCamera() {
  const track = { stop: vi.fn(), kind: 'video' as const }
  const stream = { getTracks: () => [track] } as unknown as MediaStream
  vi.stubGlobal('navigator', {
    mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) },
  })
  return track
}

function refuseCamera(name = 'NotAllowedError') {
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia: vi.fn().mockRejectedValue(Object.assign(new Error('refus'), { name })),
    },
  })
}

/** jsdom ne dessine pas : on simule juste ce que le canvas doit rendre. */
function installCanvas() {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    drawImage: vi.fn(),
  } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
    callback(new Blob([new Uint8Array([0xff, 0xd8])], { type: 'image/jpeg' }))
  })
}

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
  vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:apercu', revokeObjectURL: () => {} })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function photo(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], 'repas.jpg', { type: 'image/jpeg' })
}

describe('prise de vue', () => {
  it('ouvre la caméra dans la page', async () => {
    const user = userEvent.setup()
    installCamera()
    render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))

    expect(await screen.findByRole('button', { name: 'Prendre la photo' })).toBeInTheDocument()
  })

  it('le déclencheur produit une photo', async () => {
    const user = userEvent.setup()
    installCamera()
    installCanvas()
    // Sans dimensions, le cliché serait vide : jsdom ne les fournit pas.
    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', { value: 1920 })
    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', { value: 1080 })
    render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))
    await user.click(await screen.findByRole('button', { name: 'Prendre la photo' }))

    expect(await screen.findByRole('button', { name: 'Retirer la photo 1' })).toBeInTheDocument()
  })

  it('arrête la caméra quand l’analyse démarre', async () => {
    // Personne ne filme son assiette pendant qu'on la lui décrit.
    const user = userEvent.setup()
    const track = installCamera()
    const onAnalyze = vi.fn()
    render(<Capture onAnalyze={onAnalyze} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))
    await screen.findByRole('button', { name: 'Prendre la photo' })
    await user.upload(screen.getByLabelText('Importer une photo du repas'), photo())
    await user.click(screen.getByRole('button', { name: 'Analyser' }))

    await waitFor(() => expect(track.stop).toHaveBeenCalledTimes(1))
    expect(onAnalyze).toHaveBeenCalledTimes(1)
  })

  it('arrête la caméra à la fermeture explicite', async () => {
    const user = userEvent.setup()
    const track = installCamera()
    render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))
    await user.click(await screen.findByRole('button', { name: 'Fermer la caméra' }))

    expect(track.stop).toHaveBeenCalledTimes(1)
  })

  it('arrête la caméra quand la page est quittée', async () => {
    const user = userEvent.setup()
    const track = installCamera()
    const { unmount } = render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))
    await screen.findByRole('button', { name: 'Prendre la photo' })
    unmount()

    expect(track.stop).toHaveBeenCalledTimes(1)
  })
})

describe('l’import reste un chemin de plein droit', () => {
  it('offert même quand la caméra fonctionne', async () => {
    const user = userEvent.setup()
    installCamera()
    render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))
    await screen.findByRole('button', { name: 'Prendre la photo' })

    // Un geste ne doit jamais être l'unique moyen d'agir (spec 06 §6).
    expect(screen.getByRole('button', { name: 'Importer' })).toBeEnabled()
  })

  it('reste le chemin quand la caméra est refusée, et le dit', async () => {
    const user = userEvent.setup()
    refuseCamera()
    render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))

    expect(await screen.findByText(/L’accès à la caméra a été refusé/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Importer' })).toBeEnabled()
  })

  it('annonce l’absence de caméra sans bloquer', async () => {
    const user = userEvent.setup()
    refuseCamera('NotFoundError')
    render(<Capture onAnalyze={vi.fn()} pending={false} />)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la caméra' }))

    expect(await screen.findByText(/Aucune caméra n’a été trouvée/)).toBeInTheDocument()
  })

  it('un fichier importé devient une photo analysable', async () => {
    const user = userEvent.setup()
    installCamera()
    const onAnalyze = vi.fn()
    render(<Capture onAnalyze={onAnalyze} pending={false} />)

    await user.upload(screen.getByLabelText('Importer une photo du repas'), photo())
    await user.click(await screen.findByRole('button', { name: 'Analyser' }))

    expect(onAnalyze.mock.calls[0]?.[0]).toHaveLength(1)
  })
})
