import { useMutation } from '@tanstack/react-query'
import { LogOut, MonitorSmartphone } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { logout, logoutAll } from '@/features/auth/api'
import { useClearSession } from '@/features/auth/use-auth'
import { describeError } from '@/lib/query-client'

export function SessionSection() {
  const navigate = useNavigate()
  const clearSession = useClearSession()

  const leave = (message: string) => {
    clearSession()
    toast.success(message)
    navigate('/connexion', { replace: true })
  }

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => leave('Vous êtes déconnecté.'),
    // Même si le serveur refuse, la session locale doit être abandonnée.
    onError: (error) => {
      toast.error(describeError(error))
      leave('Session fermée localement.')
    },
  })

  const logoutAllMutation = useMutation({
    mutationFn: logoutAll,
    onSuccess: () => leave('Tous vos appareils ont été déconnectés.'),
    onError: (error) => toast.error(describeError(error)),
  })

  const busy = logoutMutation.isPending || logoutAllMutation.isPending

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h2">Sessions</CardTitle>
        <CardDescription>Gérez vos connexions à l’application.</CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-3 sm:flex-row">
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => logoutMutation.mutate()}
        >
          <LogOut aria-hidden="true" />
          Se déconnecter
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => logoutAllMutation.mutate()}
        >
          <MonitorSmartphone aria-hidden="true" />
          Déconnecter tous les appareils
        </Button>
      </CardContent>
    </Card>
  )
}
