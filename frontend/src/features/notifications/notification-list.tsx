import { CheckCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { formatDate } from '@/features/diary/dates'
import type { AppNotification } from '@/lib/api/types'
import { cn } from '@/lib/utils'

import { useMarkAllRead, useMarkRead } from './use-notifications'

function Row({ notification }: { notification: AppNotification }) {
  const markRead = useMarkRead()

  return (
    <li
      className={cn(
        'flex items-start justify-between gap-3 border-b py-3 last:border-b-0',
        !notification.is_read && 'bg-secondary/40 -mx-3 rounded-md px-3',
      )}
    >
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          {!notification.is_read && (
            <span aria-label="Non lue" className="bg-primary size-2 shrink-0 rounded-full" />
          )}
          <span className="truncate text-sm font-medium">{notification.title}</span>
        </span>
        {notification.message && (
          <span className="text-muted-foreground text-xs">{notification.message}</span>
        )}
        <span className="text-muted-foreground text-xs">
          {notification.event_label} · {formatDate(notification.created_at.slice(0, 10))}
        </span>
      </span>

      <span className="flex shrink-0 items-center gap-1">
        {notification.link && (
          <Button asChild variant="outline" size="sm">
            <Link to={notification.link}>Ouvrir</Link>
          </Button>
        )}
        {!notification.is_read && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Marquer « ${notification.title} » comme lue`}
            disabled={markRead.isPending}
            onClick={() => markRead.mutate(notification.id)}
          >
            <CheckCheck aria-hidden="true" className="size-4" />
          </Button>
        )}
      </span>
    </li>
  )
}

export function NotificationList({
  notifications,
  unread,
}: {
  notifications: AppNotification[]
  unread: number
}) {
  const markAll = useMarkAllRead()

  if (notifications.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Rien pour l’instant. Les rappels et les événements d’amis apparaîtront ici.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {unread > 0 && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          disabled={markAll.isPending}
          onClick={() =>
            markAll.mutate(undefined, {
              onSuccess: () => toast.success('Tout est lu.'),
            })
          }
        >
          <CheckCheck aria-hidden="true" className="size-4" />
          Tout marquer comme lu
        </Button>
      )}

      <ul aria-label="Notifications" className="flex flex-col">
        {notifications.map((notification) => (
          <Row key={notification.id} notification={notification} />
        ))}
      </ul>
    </div>
  )
}
