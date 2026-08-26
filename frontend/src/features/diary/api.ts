import { api } from '@/lib/api/client'
import type { Dashboard, DiaryDay, DiaryEntry, MealType } from '@/lib/api/types'

export const diaryQueryKey = ['diary'] as const
export const diaryDayQueryKey = (date: string) => ['diary', 'day', date] as const
export const mealTypesQueryKey = ['diary', 'meal-types'] as const
export const dashboardQueryKey = (date: string) => ['diary', 'dashboard', date] as const

/** Charge la journée entière : objectifs, totaux et repas (spec 04 §4). */
export const fetchDiaryDay = (date: string) => api.get<DiaryDay>('/diary/', { params: { date } })

export const fetchMealTypes = () => api.get<MealType[]>('/meal-types/')

/** Ajout d'un aliment au journal. */
export interface FoodEntryPayload {
  date: string
  meal_type_id: number
  food_id: number
  quantity: string
  unit_label: string
  consumed_at?: string
  note?: string
}

/** Ajout rapide : des calories, éventuellement des macros (spec 01 §12). */
export interface QuickAddPayload {
  date: string
  meal_type_id: number
  entry_type: 'quick_add'
  name?: string
  energy_kcal: string
  protein_g?: string | null
  carbohydrates_g?: string | null
  fat_g?: string | null
  note?: string
}

export const createEntry = (payload: FoodEntryPayload | QuickAddPayload) =>
  api.post<DiaryEntry>('/diary/entries/', payload)

export interface EntryUpdate {
  quantity?: string
  unit_label?: string
  meal_type_id?: number
  consumed_at?: string
  note?: string
}

export const updateEntry = (id: number, payload: EntryUpdate) =>
  api.patch<DiaryEntry>(`/diary/entries/${id}/`, payload)

export const deleteEntry = (id: number) => api.delete<void>(`/diary/entries/${id}/`)

/** Journée enrichie du poids, pour l'accueil (spec 04 §16). */
export const fetchDashboard = (date: string) =>
  api.get<Dashboard>('/dashboard/', { params: { date } })

/** Duplique une entrée. La copie repart de l'aliment actuel (spec 01 §5). */
export const duplicateEntry = (id: number, payload: { date?: string; meal_type_id?: number }) =>
  api.post<DiaryEntry>(`/diary/entries/${id}/duplicate/`, payload)

export const copyMeal = (payload: {
  source_date: string
  source_meal_type_id: number
  target_dates: string[]
  target_meal_type_id?: number
}) => api.post<DiaryEntry[]>('/diary/copy-meal/', payload)

export const copyDay = (payload: { source_date: string; target_dates: string[] }) =>
  api.post<DiaryEntry[]>('/diary/copy-day/', payload)

export const bulkAdd = (payload: {
  food_id: number
  meal_type_id: number
  quantity: string
  unit_label: string
  target_dates: string[]
}) => api.post<DiaryEntry[]>('/diary/bulk-add/', payload)
