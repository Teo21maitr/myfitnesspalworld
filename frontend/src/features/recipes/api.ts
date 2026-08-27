import { api } from '@/lib/api/client'
import type { DiaryEntry, Paginated, RecipeDetail, RecipeListItem } from '@/lib/api/types'

export const recipesQueryKey = ['recipes'] as const
export const recipeDetailQueryKey = (id: number) => ['recipes', 'detail', id] as const

export interface IngredientPayload {
  food_id: number
  quantity: string
  unit_label: string
}

export interface RecipePayload {
  name: string
  description?: string
  instructions?: string
  servings: string
  ingredients?: IngredientPayload[]
}

export const fetchRecipes = () => api.get<Paginated<RecipeListItem>>('/recipes/')

export const fetchRecipe = (id: number) => api.get<RecipeDetail>(`/recipes/${id}/`)

export const createRecipe = (payload: RecipePayload) => api.post<RecipeDetail>('/recipes/', payload)

export const updateRecipe = (id: number, payload: Partial<RecipePayload>) =>
  api.patch<RecipeDetail>(`/recipes/${id}/`, payload)

/** Suppression douce : l'historique du journal reste valide (spec 01 §14). */
export const deleteRecipe = (id: number) => api.delete<void>(`/recipes/${id}/`)

export const duplicateRecipe = (id: number) => api.post<RecipeDetail>(`/recipes/${id}/duplicate/`)

export const favoriteRecipe = (id: number) => api.post<void>(`/recipes/${id}/favorite/`)

export const unfavoriteRecipe = (id: number) => api.delete<void>(`/recipes/${id}/favorite/`)

/** Journalise N portions : une seule entrée, pas une par ingrédient. */
export const addRecipeToDiary = (
  id: number,
  payload: { date: string; meal_type_id: number; servings: string; note?: string },
) => api.post<DiaryEntry>(`/recipes/${id}/add-to-diary/`, payload)
