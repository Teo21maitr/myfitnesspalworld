import { api } from '@/lib/api/client'
import type {
  ExternalFoodCandidate,
  FoodDetail,
  FoodListItem,
  FoodPortion,
  Paginated,
} from '@/lib/api/types'

export const foodsQueryKey = ['foods'] as const
export const foodSearchQueryKey = (query: string) => ['foods', 'search', query] as const
export const foodDetailQueryKey = (id: number) => ['foods', 'detail', id] as const
export const myFoodsQueryKey = ['foods', 'mine'] as const
export const externalSearchQueryKey = (query: string) => ['foods', 'external', query] as const

/** Payload de création ou de modification d'un aliment personnel. */
export interface FoodPayload {
  name: string
  brand?: string
  barcode?: string | null
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

/**
 * Résout un code-barres (spec 11 §4).
 *
 * Le backend consulte d'abord les aliments personnels, puis son cache, et
 * n'interroge Open Food Facts qu'en dernier recours.
 */
export const lookupBarcode = (barcode: string) => api.get<FoodDetail>(`/barcodes/${barcode}/`)

/** Recherche élargie à Open Food Facts, jamais déclenchée à la frappe. */
export const searchExternalFoods = (query: string) =>
  api.get<{ results: ExternalFoodCandidate[] }>('/foods/external-search/', {
    params: { q: query },
  })
