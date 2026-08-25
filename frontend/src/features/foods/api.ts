import { api } from '@/lib/api/client'
import type { FoodDetail, FoodListItem, FoodPortion, Paginated } from '@/lib/api/types'

export const foodsQueryKey = ['foods'] as const
export const foodSearchQueryKey = (query: string) => ['foods', 'search', query] as const
export const foodDetailQueryKey = (id: number) => ['foods', 'detail', id] as const
export const myFoodsQueryKey = ['foods', 'mine'] as const

/** Payload de création ou de modification d'un aliment personnel. */
export interface FoodPayload {
  name: string
  brand?: string
  reference_amount: string
  reference_unit: string
  nutrition: {
    energy_kcal: string
    protein_g?: string | null
    carbohydrates_g?: string | null
    fat_g?: string | null
    fiber_g?: string | null
  }
}

export const searchFoods = (query: string) =>
  api.get<Paginated<FoodListItem>>('/foods/search/', { params: { q: query } })

export const fetchFavorites = () => api.get<Paginated<FoodListItem>>('/foods/favorites/')

export const fetchRecent = () => api.get<Paginated<FoodListItem>>('/foods/recent/')

export const fetchFrequent = () => api.get<Paginated<FoodListItem>>('/foods/frequent/')

export const fetchMyFoods = () => api.get<Paginated<FoodListItem>>('/foods/')

export const fetchFood = (id: number) => api.get<FoodDetail>(`/foods/${id}/`)

export const createFood = (payload: FoodPayload) => api.post<FoodDetail>('/foods/', payload)

export const updateFood = (id: number, payload: Partial<FoodPayload>) =>
  api.patch<FoodDetail>(`/foods/${id}/`, payload)

export const deleteFood = (id: number) => api.delete<void>(`/foods/${id}/`)

export const addFavorite = (id: number) => api.post<void>(`/foods/${id}/favorite/`)

export const removeFavorite = (id: number) => api.delete<void>(`/foods/${id}/favorite/`)

export const addPortion = (
  foodId: number,
  payload: { name: string; gram_equivalent?: string | null },
) => api.post<FoodPortion>(`/foods/${foodId}/portions/`, payload)

export const deletePortion = (foodId: number, portionId: number) =>
  api.delete<void>(`/foods/${foodId}/portions/${portionId}/`)
