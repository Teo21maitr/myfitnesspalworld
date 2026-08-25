import { useId } from 'react'
import type { FieldError, UseFormRegisterReturn } from 'react-hook-form'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface NumberFieldProps extends Omit<React.ComponentProps<'input'>, 'id' | 'type'> {
  label: string
  registration: UseFormRegisterReturn
  error?: FieldError
  hint?: string
  /** Unité affichée à droite du champ (kg, cm, kcal, g...). */
  unit?: string
}

/** Saisie numérique décimale accompagnée de son unité. */
export function NumberField({
  label,
  registration,
  error,
  hint,
  unit,
  className,
  ...props
}: NumberFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : hint ? hintId : undefined}
          className={unit ? `pr-12 ${className ?? ''}` : className}
          {...registration}
          {...props}
        />
        {unit && (
          <span
            aria-hidden="true"
            className="text-muted-foreground pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm"
          >
            {unit}
          </span>
        )}
      </div>
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
