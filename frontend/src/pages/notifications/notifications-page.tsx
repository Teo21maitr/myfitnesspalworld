import { TriangleAlert } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { NotificationList } from '@/features/notifications/notification-list'
import { PreferenceForm } from '@/features/notifications/preference-form'
import { ReminderForm } from '@/features/notifications/reminder-form'
import {
  useNotifications,
  usePreferences,
  useReminders,
} from '@/features/notifications/use-notifications'
import { describeError } from '@/lib/query-client'

function ErrorLine({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {describeError(error)}
    </p>
  )
}

function Skeleton({ label }: { label: string }) {
  return (
    <div aria-busy="true">
      <div className="bg-muted h-24 animate-pulse rounded-xl" />
      <span className="sr-only">{label}</span>
    </div>
  )
}

/** Notifications, rappels et préférences (spec 01 §24, spec 06 §4). */
export function NotificationsPage() {
  const notifications = useNotifications()
  const reminders = useReminders()
  const preferences = usePreferences()

  const rows = Array.isArray(notifications.data?.results) ? notifications.data.results : []
  const reminderRows = Array.isArray(reminders.data?.results) ? reminders.data.results : []
  const preferenceRows = Array.isArray(preferences.data?.results) ? preferences.data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Notifications</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Ce qui s’est passé, et ce que vous souhaitez qu’on vous rappelle.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Reçues
          </CardTitle>
        </CardHeader>
        <CardContent>
          {notifications.isPending && <Skeleton label="Chargement des notifications…" />}
          {notifications.error && <ErrorLine error={notifications.error} />}
          {notifications.data && (
            <NotificationList notifications={rows} unread={notifications.data.unread} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Rappels
          </CardTitle>
          <CardDescription>
            Un rappel par type, aux jours que vous choisissez. Il part au plus cinq minutes après
            l’heure indiquée.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {reminders.isPending && <Skeleton label="Chargement des rappels…" />}
          {reminders.error && <ErrorLine error={reminders.error} />}
          {reminders.data && <ReminderForm reminders={reminderRows} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Préférences
          </CardTitle>
          <CardDescription>
            Les rappels restent dans l’application par défaut : un email quotidien deviendrait vite
            du bruit.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {preferences.isPending && <Skeleton label="Chargement des préférences…" />}
          {preferences.error && <ErrorLine error={preferences.error} />}
          {preferences.data && <PreferenceForm preferences={preferenceRows} />}
        </CardContent>
      </Card>
    </div>
  )
}
