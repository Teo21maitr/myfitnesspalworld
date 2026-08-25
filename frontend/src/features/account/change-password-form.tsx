import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { FormError } from '@/components/form/form-error'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { changePassword } from '@/features/auth/api'
import { changePasswordSchema, type ChangePasswordValues } from '@/features/auth/schemas'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'

const FIELDS = ['current_password', 'new_password', 'new_password_confirmation'] as const

export function ChangePasswordForm() {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      new_password_confirmation: '',
    },
  })

  const { formError, setFormError, handleApiError } =
    useApiFormErrors<ChangePasswordValues>(setError)

  const mutation = useMutation({
    mutationFn: changePassword,
    onSuccess: (response) => {
      reset()
      toast.success(response.detail)
    },
    onError: (error) => handleApiError(error, FIELDS),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation.mutateAsync(values).catch(() => undefined)
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h2">Mot de passe</CardTitle>
        <CardDescription>
          Changer votre mot de passe déconnecte vos autres appareils.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          <FormError message={formError} />

          <TextField
            label="Mot de passe actuel"
            type="password"
            autoComplete="current-password"
            registration={register('current_password')}
            error={errors.current_password}
          />
          <TextField
            label="Nouveau mot de passe"
            type="password"
            autoComplete="new-password"
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

          <Button
            type="submit"
            className="self-start"
            disabled={isSubmitting || mutation.isPending}
          >
            {mutation.isPending ? 'Modification…' : 'Modifier le mot de passe'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
