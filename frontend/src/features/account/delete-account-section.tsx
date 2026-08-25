import { useMutation } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { FormError } from '@/components/form/form-error'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { deleteAccount } from '@/features/auth/api'
import { useClearSession } from '@/features/auth/use-auth'
import { describeError } from '@/lib/query-client'
import type { AuthUser } from '@/lib/api/types'

/**
 * Suppression définitive du compte (spec 02 §11).
 *
 * La confirmation en deux temps — ouvrir la zone, puis retaper exactement son
 * nom d'utilisateur — évite toute suppression accidentelle. Le backend
 * revalide la confirmation de son côté.
 */
export function DeleteAccountSection({ user }: { user: AuthUser }) {
  const navigate = useNavigate()
  const clearSession = useClearSession()
  const inputId = useId()

  const [confirming, setConfirming] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | undefined>()

  const mutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      clearSession()
      toast.success('Votre compte a été supprimé.')
      navigate('/connexion', { replace: true })
    },
    onError: (apiError) => setError(describeError(apiError)),
  })

  const matches = confirmation === user.username

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle as="h2" className="text-destructive">
          Supprimer mon compte
        </CardTitle>
        <CardDescription>
          La suppression est immédiate et définitive. Toutes vos données et vos sessions sont
          effacées, sans possibilité de récupération.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!confirming ? (
          <Button
            type="button"
            variant="outline"
            className="border-destructive text-destructive hover:bg-destructive/10 self-start"
            onClick={() => setConfirming(true)}
          >
            Supprimer mon compte
          </Button>
        ) : (
          <div className="flex flex-col gap-3">
            <FormError message={error} />

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={inputId}>
                Saisissez <span className="font-mono font-semibold">{user.username}</span> pour
                confirmer
              </Label>
              <Input
                id={inputId}
                value={confirmation}
                autoComplete="off"
                onChange={(event) => {
                  setConfirmation(event.target.value)
                  setError(undefined)
                }}
              />
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="destructive-outline"
                disabled={!matches || mutation.isPending}
                onClick={() => mutation.mutate(confirmation)}
              >
                {mutation.isPending ? 'Suppression…' : 'Supprimer définitivement'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setConfirming(false)
                  setConfirmation('')
                  setError(undefined)
                }}
              >
                Annuler
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
