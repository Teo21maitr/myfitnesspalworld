import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { cn } from '@/lib/utils'

import { ADD_MENU_ITEMS, BOTTOM_NAV_ITEMS, type NavItem } from './navigation'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex min-h-14 flex-col items-center justify-center gap-1 text-xs font-medium',
    isActive ? 'text-primary' : 'text-muted-foreground',
  )

function NavItemLink({ to, label, Icon, short }: NavItem) {
  return (
    <li className="flex-1">
      <NavLink to={to} end={to === '/'} className={linkClass}>
        <Icon aria-hidden="true" className="size-5" />
        {short ?? label}
      </NavLink>
    </li>
  )
}

/**
 * Barre de navigation mobile (spec 06 §2).
 *
 * Quatre raccourcis et un `+` central qui ouvre le menu d'ajout. Ce sont des
 * raccourcis vers les écrans du quotidien, pas la navigation : celle-ci vit
 * dans le tiroir, qui porte toutes les destinations.
 */
export function BottomNav() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  // Le `+` s'intercale au milieu : deux liens de chaque côté.
  const before = BOTTOM_NAV_ITEMS.slice(0, 2)
  const after = BOTTOM_NAV_ITEMS.slice(2)

  return (
    <>
      {open && (
        <>
          <button
            type="button"
            aria-label="Fermer le menu d’ajout"
            className="fixed inset-0 z-20 bg-black/40 md:hidden"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            aria-label="Ajouter"
            className="bg-background fixed inset-x-0 bottom-14 z-30 flex flex-col border-t p-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] md:hidden"
          >
            {ADD_MENU_ITEMS.map(({ to, label, Icon }) => (
              <button
                key={to}
                type="button"
                role="menuitem"
                className="hover:bg-accent flex items-center gap-3 rounded-md px-3 py-3 text-left text-sm font-medium"
                onClick={() => {
                  setOpen(false)
                  navigate(to)
                }}
              >
                <Icon aria-hidden="true" className="size-5" />
                {label}
              </button>
            ))}
          </div>
        </>
      )}

      <nav
        aria-label="Raccourcis"
        className="bg-background/95 fixed inset-x-0 bottom-0 z-30 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        <ul className="flex items-stretch justify-around">
          {before.map((item) => (
            <NavItemLink key={item.to} {...item} />
          ))}

          <li className="flex flex-1 items-center justify-center">
            <button
              type="button"
              aria-label="Ajouter"
              aria-expanded={open}
              onClick={() => setOpen((value) => !value)}
              className="bg-primary text-primary-foreground flex size-11 items-center justify-center rounded-full shadow-sm"
            >
              {open ? (
                <X aria-hidden="true" className="size-5" />
              ) : (
                <Plus aria-hidden="true" className="size-5" />
              )}
            </button>
          </li>

          {after.map((item) => (
            <NavItemLink key={item.to} {...item} />
          ))}
        </ul>
      </nav>
    </>
  )
}
