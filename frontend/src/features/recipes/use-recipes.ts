import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { diaryQueryKey } from '@/features/diary/api'
import { foodsQueryKey } from '@/features/foods/api'

import {
  addRecipeToDiary,
  createRecipe,
  deleteRecipe,
  duplicateRecipe,
  favoriteRecipe,
  fetchRecipe,
  fetchRecipes,
  recipeDetailQueryKey,
  recipesQueryKey,
  unfavoriteRecipe,
  updateRecipe,
  type RecipePayload,
} from './api'

export function useRecipes() {
  return useQuery({ queryKey: recipesQueryKey, queryFn: fetchRecipes })
}

export function useRecipe(id: number) {
  return useQuery({
    queryKey: recipeDetailQueryKey(id),
    queryFn: () => fetchRecipe(id),
    enabled: Number.isFinite(id),
  })
}

function useRecipeInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: recipesQueryKey })
  }
}

export function useCreateRecipe() {
  const invalidate = useRecipeInvalidation()

  return useMutation({
    mutationFn: (payload: RecipePayload) => createRecipe(payload),
    onSuccess: invalidate,
  })
}

export function useUpdateRecipe(id: number) {
  const invalidate = useRecipeInvalidation()

  return useMutation({
    mutationFn: (payload: Partial<RecipePayload>) => updateRecipe(id, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteRecipe() {
  const invalidate = useRecipeInvalidation()

  return useMutation({ mutationFn: (id: number) => deleteRecipe(id), onSuccess: invalidate })
}

export function useDuplicateRecipe() {
  const invalidate = useRecipeInvalidation()

  return useMutation({ mutationFn: (id: number) => duplicateRecipe(id), onSuccess: invalidate })
}

export function useToggleRecipeFavorite() {
  const invalidate = useRecipeInvalidation()

  return useMutation({
    mutationFn: ({ id, isFavorite }: { id: number; isFavorite: boolean }) =>
      isFavorite ? unfavoriteRecipe(id) : favoriteRecipe(id),
    onSuccess: invalidate,
  })
}

/**
 * Journalise une recette.
 *
 * Invalide aussi le journal et les aliments : l'entrée créée change les totaux
 * du jour, et l'accueil les affiche.
 */
export function useAddRecipeToDiary(id: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { date: string; meal_type_id: number; servings: string }) =>
      addRecipeToDiary(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: diaryQueryKey })
      void queryClient.invalidateQueries({ queryKey: foodsQueryKey })
    },
  })
}
