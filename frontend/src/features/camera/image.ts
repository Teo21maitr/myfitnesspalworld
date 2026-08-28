/**
 * Fabrication de la photo envoyée à l'analyse.
 *
 * Deux origines, une seule sortie : un fichier JPEG borné. Le cliché pris par
 * la caméra passe par `captureFrame`, le fichier choisi par l'utilisateur par
 * `prepareImage`, et les deux appliquent la même limite.
 *
 * Réduire côté client évite un aller-retour refusé et raccourcit l'attente.
 * Toute étape indisponible fait retomber sur le fichier d'origine : un
 * navigateur sans `createImageBitmap` doit pouvoir envoyer sa photo telle
 * quelle, quitte à ce que le serveur la refuse s'il la juge trop lourde.
 */

/**
 * Côté le plus long, en pixels.
 *
 * Un cliché d'iPhone récent dépasse allègrement la limite d'envoi, pour aucun
 * gain d'analyse : le modèle n'a pas besoin de douze mégapixels pour
 * reconnaître une assiette.
 */
export const MAX_SIDE = 1280

/** Qualité JPEG du ré-encodage : au-delà, le poids grimpe sans bénéfice. */
const QUALITY = 0.85

export async function prepareImage(file: File): Promise<File> {
  try {
    if (typeof createImageBitmap !== 'function') return file

    const bitmap = await createImageBitmap(file)
    const longestSide = Math.max(bitmap.width, bitmap.height)

    if (longestSide <= MAX_SIDE) {
      bitmap.close?.()
      return file
    }

    const scale = MAX_SIDE / longestSide
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)

    const context = canvas.getContext('2d')
    if (!context) return file

    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    bitmap.close?.()

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', QUALITY)
    })
    if (!blob) return file

    return new File([blob], 'repas.jpg', { type: 'image/jpeg' })
  } catch {
    return file
  }
}

/** Dimensions du cliché, ramenées sous la limite. */
function scaled(width: number, height: number): { width: number; height: number } {
  const longest = Math.max(width, height)
  if (longest <= MAX_SIDE) return { width, height }

  const scale = MAX_SIDE / longest
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

/**
 * Fige l'image courante d'un flux vidéo en fichier JPEG.
 *
 * Renvoie `null` quand le flux n'a pas encore de dimensions — la vidéo vient
 * d'être attachée — ou quand l'encodage échoue : mieux vaut ne rien produire
 * qu'un fichier vide que le serveur refuserait sans que l'utilisateur comprenne.
 */
export async function captureFrame(video: HTMLVideoElement): Promise<File | null> {
  const { videoWidth, videoHeight } = video
  if (!videoWidth || !videoHeight) return null

  try {
    const size = scaled(videoWidth, videoHeight)
    const canvas = document.createElement('canvas')
    canvas.width = size.width
    canvas.height = size.height

    const context = canvas.getContext('2d')
    if (!context) return null

    context.drawImage(video, 0, 0, size.width, size.height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', QUALITY)
    })
    if (!blob) return null

    return new File([blob], `repas-${Date.now()}.jpg`, { type: 'image/jpeg' })
  } catch {
    return null
  }
}
