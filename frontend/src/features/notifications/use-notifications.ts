import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { NotificationPreference } from '@/lib/api/types'

import {
  deleteReminder,
  fetchNotifications,
  fetchPreferences,
  fetchReminders,
  markAllRead,
  markRead,
  notificationsQueryKey,
  preferencesQueryKey,
  remindersQueryKey,
  savePreferences,
  saveReminder,
  type ReminderPayload,
} from './api'

export function useNotifications() {
  return useQuery({ queryKey: notificationsQueryKey, queryFn: fetchNotifications })
}

/**
 * Nombre de non-lues, pour la pastille de navigation.
 *
 * Lu dans la même réponse que la liste : un entier ne mérite pas sa requête.
 */
export function useUnreadCount(): number {
  const { data } = useNotifications()
  return data?.unread ?? 0
}

/**
 * Après une lecture, la liste et le tableau de bord doivent tous deux repartir
 * du serveur : sans cela une pastille éteinte se rallumerait au retour sur
 * l'accueil.
 */
function useNotificationInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: notificationsQueryKey })
    // Le tableau de bord porte le même compteur : la clé est préfixée par
    // la date, donc on invalide le préfixe commun.
    void queryClient.invalidateQueries({ queryKey: ['diary', 'dashboard'] })
  }
}

export function useMarkRead() {
  const invalidate = useNotificationInvalidation()

  return useMutation({ mutationFn: markRead, onSuccess: invalidate })
}

export function useMarkAllRead() {
  const invalidate = useNotificationInvalidation()

  return useMutation({ mutationFn: markAllRead, onSuccess: invalidate })
}

export function usePreferences() {
  return useQuery({ queryKey: preferencesQueryKey, queryFn: fetchPreferences })
}

export function useSavePreferences() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (results: NotificationPreference[]) => savePreferences(results),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: preferencesQueryKey })
    },
  })
}

export function useReminders() {
  return useQuery({ queryKey: remindersQueryKey, queryFn: fetchReminders })
}

function useReminderInvalidation() {
  const queryClient = useQueryClient()

  return () => {
    void queryClient.invalidateQueries({ queryKey: remindersQueryKey })
  }
}

export function useSaveReminder() {
  const invalidate = useReminderInvalidation()

  return useMutation({
    mutationFn: (payload: ReminderPayload) => saveReminder(payload),
    onSuccess: invalidate,
  })
}

export function useDeleteReminder() {
  const invalidate = useReminderInvalidation()

  return useMutation({ mutationFn: deleteReminder, onSuccess: invalidate })
}
