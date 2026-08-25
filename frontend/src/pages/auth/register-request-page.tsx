import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { FormError } from '@/components/form/form-error'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { requestRegistration } from '@/features/auth/api'
import { registrationSchema, type RegistrationValues } from '@/features/auth/schemas'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'

const FIELDS = [
  'first_name',
  'last_name',
  'username',
  'email',
  'password',
  'password_confirmation',
] as const

export function RegisterRequestPage() {
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegistrationValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: {
      first_name: '',
      last_name: '',
      username: '',
      email: '',
      password: '',
      password_confirmation: '',
    },
  })

  const { formError, setFormError, handleApiError } = useApiFormErrors<RegistrationValues>(setError)

  const mutation = useMutation({
    mutationFn: requestRegistration,
    onSuccess: () => navigate('/demande-envoyee', { replace: true }),
    onError: (error) => handleApiError(error, FIELDS),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation
      .mutateAsync({ ...values, email: values.email || undefined })
      .catch(() => undefined)
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h1" className="text-xl">
          Demander un compte
        </CardTitle>
        <CardDescription>
          Un administrateur devra accepter votre demande avant votre première connexion.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          <FormError message={formError} />

          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Prénom"
              autoComplete="given-name"
              registration={register('first_name')}
              error={errors.first_name}
            />
            <TextField
              label="Nom"
              autoComplete="family-name"
              registration={register('last_name')}
              error={errors.last_name}
            />
          </div>

          <TextField
            label="Nom d’utilisateur"
            autoComplete="username"
            hint="Il servira à vous connecter et à vous retrouver entre amis."
            registration={register('username')}
            error={errors.username}
          />
          <TextField
            label="Email (facultatif)"
            type="email"
            autoComplete="email"
            hint="Nécessaire uniquement pour réinitialiser votre mot de passe."
            registration={register('email')}
            error={errors.email}
          />
          <TextField
            label="Mot de passe"
            type="password"
            autoComplete="new-password"
            registration={register('password')}
            error={errors.password}
          />
          <TextField
            label="Confirmation du mot de passe"
            type="password"
            autoComplete="new-password"
            registration={register('password_confirmation')}
            error={errors.password_confirmation}
          />

          <Button type="submit" disabled={isSubmitting || mutation.isPending}>
            {mutation.isPending ? 'Envoi…' : 'Envoyer ma demande'}
          </Button>

          <p className="text-muted-foreground text-sm">
            Déjà un compte ?{' '}
            <Link to="/connexion" className="text-primary hover:underline">
              Se connecter
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  )
}
