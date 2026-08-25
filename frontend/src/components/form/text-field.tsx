import { useId } from 'react'
import type { FieldError, UseFormRegisterReturn } from 'react-hook-form'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface TextFieldProps extends Omit<React.ComponentProps<'input'>, 'id'> {
  label: string
  registration: UseFormRegisterReturn
  error?: FieldError
  hint?: string
}

/**
 * Champ de formulaire libellé.
 *
 * Chaque champ a un `label` associé et son message d'erreur est relié par
 * `aria-describedby` (spec 06 §12).
 */
export function TextField({ label, registration, error, hint, ...props }: TextFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...registration}
        {...props}
      />
      {hint && !error && (
        <p id={hintId} className="text-muted-foreground text-xs">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-destructive text-xs">
          {error.message}
        </p>
      )}
    </div>
  )
}
