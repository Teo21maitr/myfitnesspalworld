import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'

import { ErrorBoundary } from '@/components/error-boundary'
import { ThemeProvider } from '@/components/theme/theme-provider'
import { useTheme } from '@/components/theme/use-theme'
import { createQueryClient } from '@/lib/query-client'

import { router } from './router'

function ThemedToaster() {
  const { resolvedTheme } = useTheme()
  return <Toaster theme={resolvedTheme} position="top-center" richColors closeButton />
}

export function App() {
  // Le QueryClient est créé une seule fois par montage de l'application.
  const [queryClient] = useState(createQueryClient)

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          <ThemedToaster />
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}
