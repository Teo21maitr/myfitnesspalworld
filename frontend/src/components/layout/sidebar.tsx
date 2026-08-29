import { NavList } from './nav-list'

/** Barre latérale desktop (spec 06 §3). */
export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 border-r md:block">
      <nav aria-label="Navigation principale" className="sticky top-0 overflow-y-auto p-4">
        <NavList />
      </nav>
    </aside>
  )
}
