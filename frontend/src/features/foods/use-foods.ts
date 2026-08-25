import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { FoodDetail, FoodListItem, Paginated } from '@/lib/api/types'

import {
  addFavorite,
  createFood,
  deleteFood,
  fetchFavorites,
  fetchFood,
  fetchFrequent,
  fetchMyFoods,
  fetchRecent,
  foodDetailQueryKey,
  foodSearchQueryKey,
  foodsQueryKey,
  myFoodsQueryKey,
  removeFavorite,
  searchFoods,
  updateFood,
  type FoodPayload,
} from './api'

/** La recherche ne se déclenche qu'à partir de deux caractères (spec 01 §7). */
export const MINIMUM_QUERY_LENGTH = 2

export function useFoodSearch(query: string) {
  const trimmed = query.trim()

  return useQuery({
    queryKey: foodSearchQueryKey(trimmed),
    queryFn: () => searchFoods(trimmed),
    enabled: trimmed.length >= MINIMUM_QUERY_LENGTH,
    staleTime: 60_000,
  })
}

/** Listes affichées tant que l'utilisateur n'a pas saisi de requête. */
export function useFoodShortcuts() {
  const favorites = useQuery({
    queryKey: [...foodsQueryKey, 'favorites'],
    queryFn: fetchFavorites,
  })
  const recent = useQuery({ queryKey: [...foodsQueryKey, 'recent'], queryFn: fetchRecent })
  const frequent = useQuery({
    queryKey: [...foodsQueryKey, 'frequent'],
    queryFn: fetchFrequent,
  })

  return { favorites, recent, frequent }
}

export function useFood(id: number) {
  return useQuery({ queryKey: foodDetailQueryKey(id), queryFn: () => fetchFood(id) })
}

export function useMyFoods() {
  return useQuery({ queryKey: myFoodsQueryKey, queryFn: fetchMyFoods })
}

/**
 * Bascule de favori, avec mise à jour optimiste.
 *
 * L'étoile réagit immédiatement ; en cas d'échec, l'état précédent est
 * restauré et l'erreur remonte par le gestionnaire global.
 */
export function useToggleFavorite() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, isFavorite }: { id: number; isFavorite: boolean }) =>
      isFavorite ? removeFavorite(id) : addFavorite(id),

    onMutate: async ({ id, isFavorite }) => {
      await queryClient.cancelQueries({ queryKey: foodsQueryKey })
      const snapshot = queryClient.getQueriesData<Paginated<FoodListItem>>({
        queryKey: foodsQueryKey,
      })

      // Le préfixe `['foods']` couvre aussi la fiche détail, qui n'est pas
      // paginée : seules les listes sont réécrites.
      queryClient.setQueriesData<Paginated<FoodListItem>>({ queryKey: foodsQueryKey }, (page) =>
        page && Array.isArray(page.results)
          ? {
              ...page,
              results: page.results.map((food) =>
                food.id === id ? { ...food, is_favorite: !isFavorite } : food,
              ),
            }
          : page,
      )

      queryClient.setQueryData<FoodDetail>(foodDetailQueryKey(id), (food) =>
        food ? { ...food, is_favorite: !isFavorite } : food,
      )

      return { snapshot }
    },

    onError: (_error, _variables, context) => {
      context?.snapshot.forEach(([key, data]) => queryClient.setQueryData(key, data))
    },

    onSettled: () => queryClient.invalidateQueries({ queryKey: foodsQueryKey }),
  })
}

function useFoodInvalidation() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: foodsQueryKey })
}

export function useCreateFood() {
  const invalidate = useFoodInvalidation()
  return useMutation({ mutationFn: createFood, onSuccess: invalidate })
}

export function useUpdateFood(id: number) {
  const invalidate = useFoodInvalidation()
  return useMutation({
    mutationFn: (payload: Partial<FoodPayload>) => updateFood(id, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteFood() {
  const invalidate = useFoodInvalidation()
  return useMutation({ mutationFn: deleteFood, onSuccess: invalidate })
}
