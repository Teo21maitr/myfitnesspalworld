import { api } from '@/lib/api/client'
import type { DiaryEntry, Paginated, SavedMeal } from '@/lib/api/types'

export const savedMealsQueryKey = ['saved-meals'] as const
export const savedMealQueryKey = (id: number) => ['saved-meals', 'detail', id] as const

export interface SavedMealItemPayload {
  item_type: 'food' | 'recipe'
  food_id?: number
  recipe_id?: number
  quantity: string
  unit_label?: string
}

export interface SavedMealPayload {
  name: string
  description?: string
  items?: SavedMealItemPayload[]
}

/** Réponse de l'ajout au journal : les éléments dont la source a disparu sont nommés. */
export interface SavedMealAddResult {
  entries: DiaryEntry[]
  skipped: string[]
}

export const fetchSavedMeals = () => api.get<Paginated<SavedMeal>>('/saved-meals/')

export const fetchSavedMeal = (id: number) => api.get<SavedMeal>(`/saved-meals/${id}/`)

export const createSavedMeal = (payload: SavedMealPayload) =>
  api.post<SavedMeal>('/saved-meals/', payload)

export const updateSavedMeal = (id: number, payload: Partial<SavedMealPayload>) =>
  api.patch<SavedMeal>(`/saved-meals/${id}/`, payload)

export const deleteSavedMeal = (id: number) => api.delete<void>(`/saved-meals/${id}/`)

export const duplicateSavedMeal = (id: number) =>
  api.post<SavedMeal>(`/saved-meals/${id}/duplicate/`)

export const addSavedMealToDiary = (id: number, payload: { date: string; meal_type_id: number }) =>
  api.post<SavedMealAddResult>(`/saved-meals/${id}/add-to-diary/`, payload)
