import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'

import { Button } from '@/components/ui/button'

import { NavList } from './nav-list'

/**
 * Tiroir de navigation mobile (spec 06 §1-2).
 *
 * La barre du bas ne porte que quatre raccourcis ; tout le reste vit ici, dans
 * la même liste que la barre latérale desktop. Sans lui, une destination
 * absente des quatre raccourcis devenait inatteignable au doigt — c'est
 * exactement ce qui était arrivé à « Mes repas ».
 */
export function NavDrawer() {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Un changement de page ferme le tiroir, y compris quand il vient d'ailleurs
  // — un retour arrière, par exemple. Ajusté pendant le rendu plutôt que dans
  // un effet : un effet déclencherait un rendu en cascade pour une valeur qui
  // se déduit déjà de la route.
  const [shownFor, setShownFor] = useState(location.pathname)
  if (shownFor !== location.pathname) {
    setShownFor(location.pathname)
    setOpen(false)
  }

  return (
    <div className="md:hidden">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Ouvrir la navigation"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <Menu aria-hidden="true" className="size-5" />
      </Button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Fermer la navigation"
            className="fixed inset-0 z-40 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <nav
            aria-label="Menu de navigation"
            className="bg-background fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r"
          >
            <div className="flex items-center justify-between border-b px-4 py-3">
              <span className="font-semibold tracking-tight">Navigation</span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Fermer la navigation"
                onClick={() => setOpen(false)}
              >
                <X aria-hidden="true" className="size-5" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
              <NavList onNavigate={() => setOpen(false)} />
            </div>
          </nav>
        </>
      )}
    </div>
  )
}
