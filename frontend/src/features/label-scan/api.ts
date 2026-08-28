import { api } from '@/lib/api/client'
import type { LabelScanTask } from '@/lib/api/types'

/** Nom du champ attendu par le backend pour les photos. */
const IMAGES_FIELD = 'images'

/**
 * Lance la lecture d'une étiquette nutritionnelle (spec 04 §10).
 *
 * Rend un brouillon, jamais un aliment : c'est l'utilisateur qui crée la
 * fiche, après avoir vérifié ce que la photo a donné (spec 01 §11).
 */
export const startLabelScan = (images: File[]) => {
  const body = new FormData()
  for (const image of images) {
    body.append(IMAGES_FIELD, image)
  }
  // `json` laissé indéfini : le navigateur doit poser lui-même le type
  // multipart et sa frontière.
  return api.post<LabelScanTask>('/ai/label-scan/', undefined, { body })
}
