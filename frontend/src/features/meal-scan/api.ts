import { api } from '@/lib/api/client'
import type { AIStatus, MealScanTask } from '@/lib/api/types'

export const taskQueryKey = (id: string) => ['tasks', id] as const
export const aiStatusQueryKey = ['ai', 'status'] as const

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

export const fetchMealScanTask = (id: string) => api.get<MealScanTask>(`/tasks/${id}/`)

/**
 * L'IA est-elle disponible ?
 *
 * Interrogée à l'ouverture de l'écran : apprendre qu'une fonctionnalité est
 * éteinte après avoir cadré sa photo est une mauvaise façon de l'apprendre.
 */
export const fetchAIStatus = () => api.get<AIStatus>('/ai/status/')
