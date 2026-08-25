import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { FormError } from '@/components/form/form-error'
import { TextField } from '@/components/form/text-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { meQueryKey, updateProfile } from '@/features/auth/api'
import { profileSchema, type ProfileValues } from '@/features/auth/schemas'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'
import type { AuthUser } from '@/lib/api/types'

const FIELDS = ['first_name', 'last_name', 'username', 'email'] as const

export function ProfileForm({ user }: { user: AuthUser }) {
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      first_name: user.first_name,
      last_name: user.last_name,
      username: user.username,
      email: user.email ?? '',
    },
  })

  const { formError, setFormError, handleApiError } = useApiFormErrors<ProfileValues>(setError)

  const mutation = useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(meQueryKey, profile)
      reset({
        first_name: profile.first_name,
        last_name: profile.last_name,
        username: profile.username,
        email: profile.email ?? '',
      })
      toast.success('Profil mis à jour.')
    },
    onError: (error) => handleApiError(error, FIELDS),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined)
    return mutation.mutateAsync({ ...values, email: values.email || null }).catch(() => undefined)
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle as="h2">Mes informations</CardTitle>
        <CardDescription>Votre identité dans l’application.</CardDescription>
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
            registration={register('username')}
            error={errors.username}
          />
          <TextField
            label="Email (facultatif)"
            type="email"
            autoComplete="email"
            hint="Sans email, seul un administrateur peut réinitialiser votre mot de passe."
            registration={register('email')}
            error={errors.email}
          />

          <Button
            type="submit"
            className="self-start"
            disabled={!isDirty || isSubmitting || mutation.isPending}
          >
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
