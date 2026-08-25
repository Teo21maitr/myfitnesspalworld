import { useCallback, useState } from 'react'
import type { FieldValues, UseFormSetError } from 'react-hook-form'

import { ApiError } from '@/lib/api/client'
import { describeError } from '@/lib/query-client'

/**
 * Rapproche les erreurs de l'API des champs du formulaire.
 *
 * Le backend renvoie `{code, message, errors: {champ: [messages]}}` : chaque
 * champ connu du formulaire reçoit son message, le reste est affiché comme
 * erreur globale (spec 10 §12).
 */
export function useApiFormErrors<T extends FieldValues>(setError: UseFormSetError<T>) {
  const [formError, setFormError] = useState<string | undefined>()

  const handleApiError = useCallback(
    (error: unknown, knownFields: readonly (keyof T & string)[]) => {
      if (error instanceof ApiError) {
        let matched = false

        for (const field of knownFields) {
          const message = error.fieldError(field)
          if (message) {
            matched = true
            setError(field as Parameters<UseFormSetError<T>>[0], { type: 'server', message })
          }
        }

        const nonFieldMessages = error.errors['non_field_errors']
        setFormError(
          matched && !nonFieldMessages ? undefined : (nonFieldMessages?.[0] ?? error.message),
        )
        return
      }

      setFormError(describeError(error))
    },
    [setError],
  )

  return { formError, setFormError, handleApiError }
}
