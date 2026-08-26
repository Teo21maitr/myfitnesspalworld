import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/utils'

import { SIDEBAR_NAV_ITEMS } from './navigation'

/** Barre latérale desktop (spec 06 §3). */
export function Sidebar() {
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
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
