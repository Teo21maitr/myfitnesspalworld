import { QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'

import { ErrorBoundary } from '@/components/error-boundary'
import { ThemeProvider } from '@/components/theme/theme-provider'
import { useTheme } from '@/components/theme/use-theme'
import { meQueryKey } from '@/features/auth/api'
import { setUnauthorizedHandler } from '@/lib/api/client'
import { createQueryClient } from '@/lib/query-client'

import { router } from './router'

function ThemedToaster() {
  const { resolvedTheme } = useTheme()
  return <Toaster theme={resolvedTheme} position="top-center" richColors closeButton />
}

export function App() {
  // Le QueryClient est créé une seule fois par montage de l'application.
  const [queryClient] = useState(createQueryClient)

  useEffect(() => {
    // Quand le rafraîchissement silencieux échoue, la session est perdue :
    // l'état local est vidé et les gardes de route renvoient vers /connexion.
    setUnauthorizedHandler(() => {
      queryClient.setQueryData(meQueryKey, null)
    })
    return () => setUnauthorizedHandler(null)
  }, [queryClient])

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
