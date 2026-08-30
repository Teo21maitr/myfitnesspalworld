import { NavLink } from 'react-router-dom'

import { usePendingRequestCount } from '@/features/friends/use-friends'
import { useUnreadCount } from '@/features/notifications/use-notifications'
import { cn } from '@/lib/utils'

import { NAV_SECTIONS } from './navigation'

/** Pastille d'attente, partagée par les entrées qui en portent une. */
function Badge({ count, label }: { count: number; label: string }) {
  if (count <= 0) return null

  return (
    <span
      aria-label={label}
      className="bg-primary text-primary-foreground ml-auto rounded-full px-1.5 text-xs"
    >
      {count}
    </span>
  )
}

/**
 * La navigation, rendue une seule fois pour deux emplacements.
 *
 * La barre latérale et le tiroir mobile partagent ce composant : c'est ce qui
 * garantit qu'une destination ajoutée apparaît des deux côtés (spec 06 §1).
 */
export function NavList({ onNavigate }: { onNavigate?: () => void }) {
  // Deux compteurs, deux entrées. Les demandes d'ami gardent le leur : elles
  // produisent désormais une notification, mais la page Amis reste l'endroit
  // où l'on y répond.
  const pendingRequests = usePendingRequestCount()
  const unread = useUnreadCount()

  return (
    <ul className="flex flex-col gap-4">
      {NAV_SECTIONS.map((section) => (
        <li key={section.title}>
          <p className="text-muted-foreground px-3 pb-1 text-xs font-medium tracking-wide uppercase">
            {section.title}
          </p>
          <ul className="flex flex-col gap-0.5">
            {section.items.map(({ to, label, Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      'flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium',
                      isActive
                        ? 'bg-secondary text-secondary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    )
                  }
                >
                  <Icon aria-hidden="true" className="size-4 shrink-0" />
                  {label}
                  {to === '/amis' && (
                    <Badge
                      count={pendingRequests}
                      label={`${pendingRequests} demande${pendingRequests > 1 ? 's' : ''} en attente`}
                    />
                  )}
                  {to === '/notifications' && (
                    <Badge
                      count={unread}
                      label={`${unread} notification${unread > 1 ? 's' : ''} non lue${unread > 1 ? 's' : ''}`}
                    />
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  )
}
