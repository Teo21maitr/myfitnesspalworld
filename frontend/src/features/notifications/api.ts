import { api } from '@/lib/api/client'
import type {
  AppNotification,
  NotificationPreference,
  Paginated,
  Reminder,
  ReminderType,
} from '@/lib/api/types'

export const notificationsQueryKey = ['notifications'] as const
export const preferencesQueryKey = ['notifications', 'preferences'] as const
export const remindersQueryKey = ['notifications', 'reminders'] as const

/** La liste porte son compteur de non-lues : une requête suffit. */
export type NotificationPage = Paginated<AppNotification> & { unread: number }

export const fetchNotifications = () => api.get<NotificationPage>('/notifications/')

export const markRead = (id: number) => api.post<AppNotification>(`/notifications/${id}/read/`)

export const markAllRead = () => api.post<{ updated: number }>('/notifications/read-all/')

export const fetchPreferences = () =>
  api.get<{ results: NotificationPreference[] }>('/notification-preferences/')

export const savePreferences = (results: NotificationPreference[]) =>
  api.patch<{ results: NotificationPreference[] }>('/notification-preferences/', { results })

export const fetchReminders = () => api.get<Paginated<Reminder>>('/reminders/')

export interface ReminderPayload {
  reminder_type: ReminderType
  time: string
  days_of_week: number[]
  enabled?: boolean
}

/** Un second envoi sur un type déjà réglé met à jour : il ne se refuse pas. */
export const saveReminder = (payload: ReminderPayload) => api.post<Reminder>('/reminders/', payload)

export const deleteReminder = (id: number) => api.delete<void>(`/reminders/${id}/`)
