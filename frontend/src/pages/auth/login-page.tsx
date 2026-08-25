import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { FormError } from '@/components/form/form-error'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { login, meQueryKey } from '@/features/auth/api'
import { loginSchema, type LoginValues } from '@/features/auth/schemas'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '' },
  })

  const { formError, setFormError, handleApiError } = useApiFormErrors<LoginValues>(setError)

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      queryClient.setQueryData(meQueryKey, user)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? '/', { replace: true })
    },
    onError: (error) => handleApiError(error, ['username', 'password']),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation.mutateAsync(values).catch(() => undefined)
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h1" className="text-xl">
          Connexion
        </CardTitle>
        <CardDescription>Accédez à votre suivi alimentaire.</CardDescription>
      </CardHeader>

      <CardContent>
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          <FormError message={formError} />

          <TextField
            label="Nom d’utilisateur"
            autoComplete="username"
            autoFocus
            registration={register('username')}
            error={errors.username}
          />
          <TextField
            label="Mot de passe"
            type="password"
            autoComplete="current-password"
            registration={register('password')}
            error={errors.password}
          />

          <Button type="submit" disabled={isSubmitting || mutation.isPending}>
            {mutation.isPending ? 'Connexion…' : 'Se connecter'}
          </Button>

          <div className="flex flex-col gap-2 text-sm">
            <Link to="/mot-de-passe-oublie" className="text-primary hover:underline">
              Mot de passe oublié ?
            </Link>
            <span className="text-muted-foreground">
              Pas encore de compte ?{' '}
              <Link to="/demande-inscription" className="text-primary hover:underline">
                Demander un compte
              </Link>
            </span>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
