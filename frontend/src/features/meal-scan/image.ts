/**
 * Réduction d'une photo avant envoi.
 *
 * Une photo d'iPhone récent dépasse allègrement la limite d'envoi, pour aucun
 * gain d'analyse : le modèle n'a pas besoin de douze mégapixels pour
 * reconnaître une assiette. La réduire côté client évite un aller-retour
 * refusé et raccourcit l'attente.
 *
 * Toute étape indisponible fait retomber sur le fichier d'origine : un
 * navigateur sans `createImageBitmap` doit pouvoir envoyer sa photo telle
 * quelle, quitte à ce que le serveur la refuse s'il la juge trop lourde.
 */

/** Côté le plus long après réduction, en pixels. */
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
