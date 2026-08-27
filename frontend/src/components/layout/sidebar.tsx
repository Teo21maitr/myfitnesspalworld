import { NavLink } from 'react-router-dom'

import { usePendingRequestCount } from '@/features/friends/use-friends'
import { cn } from '@/lib/utils'

import { SIDEBAR_NAV_ITEMS } from './navigation'

/** Barre latérale desktop (spec 06 §3). */
export function Sidebar() {
  // Une demande d'ami arrive sans notification : la pastille est le seul
  // signal, tant que le modèle `Notification` n'existe pas.
  const pendingRequests = usePendingRequestCount()

  return (
    <aside className="hidden w-60 shrink-0 border-r md:block">
      <nav aria-label="Navigation principale" className="sticky top-0 p-4">
        <ul className="flex flex-col gap-1">
          {SIDEBAR_NAV_ITEMS.map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium',
                    isActive
                      ? 'bg-secondary text-secondary-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  )
                }
              >
                <Icon aria-hidden="true" className="size-4" />
                {label}
                {to === '/amis' && pendingRequests > 0 && (
                  <span
                    aria-label={`${pendingRequests} demande${pendingRequests > 1 ? 's' : ''} en attente`}
                    className="bg-primary text-primary-foreground ml-auto rounded-full px-1.5 text-xs"
                  >
                    {pendingRequests}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
