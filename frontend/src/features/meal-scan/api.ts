import { api } from '@/lib/api/client'
import type { MealScanTask } from '@/lib/api/types'

/** Nom du champ attendu par le backend pour les photos. */
const IMAGES_FIELD = 'images'

/**
 * Lance l'analyse d'une photo de repas (spec 04 §10).
 *
 * Répond immédiatement avec une tâche : l'analyse se poursuit côté serveur.
 * Aucune entrée de journal n'est créée ici — les suggestions attendent une
 * confirmation (spec 07 §5).
 */
export const startMealScan = (images: File[]) => {
  const body = new FormData()
  for (const image of images) {
    body.append(IMAGES_FIELD, image)
  }
  // `json` laissé indéfini : le navigateur doit poser lui-même le type
  // multipart et sa frontière.
  return api.post<MealScanTask>('/ai/meal-scan/', undefined, { body })
}
