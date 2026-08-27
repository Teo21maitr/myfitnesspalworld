import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addShoppingItem,
  createShoppingList,
  deleteShoppingItem,
  deleteShoppingList,
  fetchShoppingList,
  fetchShoppingLists,
  generateShoppingList,
  renameShoppingList,
  shoppingListQueryKey,
  shoppingQueryKey,
  updateShoppingItem,
  type GeneratePayload,
  type ItemPayload,
} from './api'

export function useShoppingLists() {
  return useQuery({ queryKey: shoppingQueryKey, queryFn: fetchShoppingLists })
}

export function useShoppingList(id: number) {
  return useQuery({
    queryKey: shoppingListQueryKey(id),
    queryFn: () => fetchShoppingList(id),
    enabled: Number.isFinite(id),
  })
}

function useShoppingInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: shoppingQueryKey })
  }
}

export function useCreateShoppingList() {
  const invalidate = useShoppingInvalidation()

  return useMutation({
    mutationFn: (payload: { name: string }) => createShoppingList(payload),
    onSuccess: invalidate,
  })
}

export function useRenameShoppingList(id: number) {
  const invalidate = useShoppingInvalidation()

  return useMutation({
    mutationFn: (payload: { name: string }) => renameShoppingList(id, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteShoppingList() {
  const invalidate = useShoppingInvalidation()

  return useMutation({ mutationFn: (id: number) => deleteShoppingList(id), onSuccess: invalidate })
}

export function useGenerateShoppingList() {
  const invalidate = useShoppingInvalidation()

  return useMutation({
    mutationFn: (payload: GeneratePayload) => generateShoppingList(payload),
    onSuccess: invalidate,
  })
}

export function useAddShoppingItem(listId: number) {
  const invalidate = useShoppingInvalidation()

  return useMutation({
    mutationFn: (payload: ItemPayload) => addShoppingItem(listId, payload),
    onSuccess: invalidate,
  })
}

export function useUpdateShoppingItem(listId: number) {
  const invalidate = useShoppingInvalidation()

  return useMutation({
    mutationFn: ({
      itemId,
      ...payload
    }: {
      itemId: number
      name?: string
      quantity?: string | null
      is_checked?: boolean
    }) => updateShoppingItem(listId, itemId, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteShoppingItem(listId: number) {
  const invalidate = useShoppingInvalidation()

  return useMutation({
    mutationFn: (itemId: number) => deleteShoppingItem(listId, itemId),
    onSuccess: invalidate,
  })
}
