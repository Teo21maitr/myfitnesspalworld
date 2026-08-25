import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router-dom'

import { FormError } from '@/components/form/form-error'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { resetPassword } from '@/features/auth/api'
import { resetPasswordSchema, type ResetPasswordValues } from '@/features/auth/schemas'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const uid = searchParams.get('uid') ?? ''
  const token = searchParams.get('token') ?? ''

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: '', new_password_confirmation: '' },
  })

  const { formError, setFormError, handleApiError } =
    useApiFormErrors<ResetPasswordValues>(setError)

  const mutation = useMutation({
    mutationFn: resetPassword,
    onError: (error) => handleApiError(error, ['new_password', 'new_password_confirmation']),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation.mutateAsync({ ...values, uid, token }).catch(() => undefined)
  })

  if (!uid || !token) {
    return (
      <Card>
        <CardHeader>
          <CardTitle as="h1" className="text-xl">
            Lien invalide
          </CardTitle>
          <CardDescription>Ce lien de réinitialisation est incomplet.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link to="/mot-de-passe-oublie">Demander un nouveau lien</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (mutation.isSuccess) {
    return (
      <Card>
        <CardHeader>
          <CheckCircle2 aria-hidden="true" className="text-success size-8" />
          <CardTitle as="h1" className="text-xl">
            Mot de passe modifié
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm">{mutation.data.detail}</p>
          <Button asChild className="self-start">
            <Link to="/connexion">Se connecter</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h1" className="text-xl">
          Nouveau mot de passe
        </CardTitle>
        <CardDescription>Choisissez un mot de passe pour votre compte.</CardDescription>
      </CardHeader>

      <CardContent>
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          <FormError message={formError} />

          <TextField
            label="Nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            autoFocus
            registration={register('new_password')}
            error={errors.new_password}
          />
          <TextField
            label="Confirmation"
            type="password"
            autoComplete="new-password"
            registration={register('new_password_confirmation')}
            error={errors.new_password_confirmation}
          />

          <Button type="submit" disabled={isSubmitting || mutation.isPending}>
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>

          <Link to="/mot-de-passe-oublie" className="text-primary text-sm hover:underline">
            Demander un nouveau lien
          </Link>
        </form>
      </CardContent>
    </Card>
  )
}
