import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { MailCheck } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'

import { FormError } from '@/components/form/form-error'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { forgotPassword } from '@/features/auth/api'
import { forgotPasswordSchema, type ForgotPasswordValues } from '@/features/auth/schemas'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'

export function ForgotPasswordPage() {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { username: '' },
  })

  const { formError, setFormError, handleApiError } =
    useApiFormErrors<ForgotPasswordValues>(setError)

  const mutation = useMutation({
    mutationFn: forgotPassword,
    onError: (error) => handleApiError(error, ['username']),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation.mutateAsync(values.username).catch(() => undefined)
  })

  if (mutation.isSuccess) {
    return (
      <Card>
        <CardHeader>
          <MailCheck aria-hidden="true" className="text-primary size-8" />
          <CardTitle as="h1" className="text-xl">
            Demande enregistrée
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {/* Message volontairement neutre : il ne révèle pas si un compte
              existe ni s'il possède une adresse email (spec 05 §12). */}
          <p className="text-sm">{mutation.data.detail}</p>
          <Button asChild variant="outline" className="self-start">
            <Link to="/connexion">Retour à la connexion</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h1" className="text-xl">
          Mot de passe oublié
        </CardTitle>
        <CardDescription>
          Indiquez votre nom d’utilisateur pour recevoir un lien de réinitialisation.
        </CardDescription>
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

          <Button type="submit" disabled={isSubmitting || mutation.isPending}>
            {mutation.isPending ? 'Envoi…' : 'Envoyer le lien'}
          </Button>

          <Link to="/connexion" className="text-primary text-sm hover:underline">
            Retour à la connexion
          </Link>
        </form>
      </CardContent>
    </Card>
  )
}
