import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom'

import { ThemeProvider } from '@/components/theme/theme-provider'
import { routes } from '@/router'

/** QueryClient silencieux et déterministe pour les tests. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

function Providers({ children, queryClient }: { children: ReactNode; queryClient: QueryClient }) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  )
}

export function renderWithProviders(
  ui: ReactElement,
  {
    queryClient = createTestQueryClient(),
    ...options
  }: RenderOptions & { queryClient?: QueryClient } = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <Providers queryClient={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </Providers>
    )
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) }
}

/**
 * Monte l'arbre de routes réel de l'application.
 *
 * Indispensable pour vérifier les gardes de route et les redirections.
 */
export function renderRoute(
  initialPath = '/',
  { queryClient = createTestQueryClient() }: { queryClient?: QueryClient } = {},
) {
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })

  const result = render(
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>,
  )

  return { ...result, router, queryClient }
}
