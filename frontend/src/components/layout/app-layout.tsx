import { Outlet } from 'react-router-dom'

import { ThemeToggle } from '@/components/theme/theme-toggle'

import { BottomNav } from './bottom-nav'
import { OfflineBanner } from './offline-banner'
import { Sidebar } from './sidebar'

/** Coquille applicative : mobile-first, sidebar à partir de `md`. */
export function AppLayout() {
  return (
    <div className="flex min-h-full flex-col">
      <OfflineBanner />

      <header className="flex items-center justify-between gap-4 border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <img src="/favicon.svg" alt="" aria-hidden="true" className="size-7 rounded-md" />
          <span className="font-semibold tracking-tight">MyFitnessPalworld</span>
        </div>
        <ThemeToggle />
      </header>

      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 px-4 py-6 pb-24 md:pb-6">
          <Outlet />
        </main>
      </div>

      <BottomNav />
    </div>
  )
}
