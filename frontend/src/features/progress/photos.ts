import { api } from '@/lib/api/client'
import type { Paginated, PhotoType, ProgressPhotoGroup } from '@/lib/api/types'

export const photosQueryKey = ['progress', 'photos'] as const

/** Les quatre angles de la spec 01 §20. */
export const PHOTO_TYPES: readonly { value: PhotoType; label: string }[] = [
  { value: 'front', label: 'Face' },
  { value: 'side', label: 'Profil' },
  { value: 'back', label: 'Dos' },
  { value: 'other', label: 'Autre' },
] as const

/** Quatre angles, donc quatre photos par envoi. Aligné sur le backend. */
export const MAX_PHOTOS = 4

export interface PhotoUpload {
  file: File
  photo_type: PhotoType
}

export const fetchPhotoGroups = () => api.get<Paginated<ProgressPhotoGroup>>('/progress/photos/')

/**
 * Envoie une ou plusieurs photos pour une date.
 *
 * Les angles voyagent dans un champ parallèle, **dans le même ordre** que les
 * fichiers : `FormData` conserve l'ordre d'insertion, et le backend apparie
 * par position.
 */
export const uploadPhotos = (payload: {
  date: string
  photos: PhotoUpload[]
  notes?: string
  weight_kg_snapshot?: string
}) => {
  const body = new FormData()
  body.append('date', payload.date)
  if (payload.notes) body.append('notes', payload.notes)
  if (payload.weight_kg_snapshot) body.append('weight_kg_snapshot', payload.weight_kg_snapshot)

  for (const { file, photo_type } of payload.photos) {
    body.append('photos', file)
    body.append('photo_types', photo_type)
  }

  // `json` laissé indéfini : le navigateur pose lui-même le type multipart et
  // sa frontière.
  return api.post<ProgressPhotoGroup>('/progress/photos/', undefined, { body })
}

export const deletePhotoGroup = (id: number) => api.delete<void>(`/progress/photos/${id}/`)

export const deletePhoto = (groupId: number, photoId: number) =>
  api.delete<void>(`/progress/photos/${groupId}/files/${photoId}/`)
