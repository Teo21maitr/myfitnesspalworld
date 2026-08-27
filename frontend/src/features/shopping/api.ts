import { api } from '@/lib/api/client'
import type { Paginated, ShoppingList, ShoppingListItem } from '@/lib/api/types'

export const shoppingQueryKey = ['shopping-lists'] as const
export const shoppingListQueryKey = (id: number) => ['shopping-lists', 'detail', id] as const

export interface GeneratePayload {
  /** Sans elle, une liste est créée ; avec elle, elle est complétée. */
  shopping_list_id?: number
  name?: string
  recipe_ids?: number[]
  dates?: string[]
}

export interface ItemPayload {
  name: string
  quantity?: string | null
  unit_label?: string | null
}

export const fetchShoppingLists = () => api.get<Paginated<ShoppingList>>('/shopping-lists/')

export const fetchShoppingList = (id: number) => api.get<ShoppingList>(`/shopping-lists/${id}/`)

export const createShoppingList = (payload: { name: string }) =>
  api.post<ShoppingList>('/shopping-lists/', payload)

export const renameShoppingList = (id: number, payload: { name: string }) =>
  api.patch<ShoppingList>(`/shopping-lists/${id}/`, payload)

/** Suppression franche : une liste est un brouillon (spec 01 §16). */
export const deleteShoppingList = (id: number) => api.delete<void>(`/shopping-lists/${id}/`)

/** Les articles compatibles fusionnent, quantités converties d'abord. */
export const generateShoppingList = (payload: GeneratePayload) =>
  api.post<ShoppingList>('/shopping-lists/generate/', payload)

export const addShoppingItem = (listId: number, payload: ItemPayload) =>
  api.post<ShoppingListItem>(`/shopping-lists/${listId}/items/`, payload)

export const updateShoppingItem = (
  listId: number,
  itemId: number,
  payload: Partial<Pick<ShoppingListItem, 'name' | 'quantity' | 'is_checked'>>,
) => api.patch<ShoppingListItem>(`/shopping-lists/${listId}/items/${itemId}/`, payload)

export const deleteShoppingItem = (listId: number, itemId: number) =>
  api.delete<void>(`/shopping-lists/${listId}/items/${itemId}/`)
