import { Outlet } from 'react-router-dom'

import { ThemeToggle } from '@/components/theme/theme-toggle'

import { OfflineBanner } from './offline-banner'

/** Coquille des écrans publics : carte centrée, mobile-first. */
export function AuthLayout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <OfflineBanner />

      <header className="flex items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-2">
          <img src="/favicon.svg" alt="" aria-hidden="true" className="size-7 rounded-md" />
          <span className="font-semibold tracking-tight">MyFitnessPalworld</span>
        </div>
        <ThemeToggle />
      </header>

      <main className="flex flex-1 items-start justify-center px-4 py-6 sm:items-center">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
