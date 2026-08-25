import { useId } from 'react'
import type { FieldError, UseFormRegisterReturn } from 'react-hook-form'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: string
}

interface SelectFieldProps extends Omit<React.ComponentProps<'select'>, 'id' | 'children'> {
  label: string
  options: readonly SelectOption[]
  registration: UseFormRegisterReturn
  error?: FieldError
  hint?: string
  placeholder?: string
}

/**
 * Liste déroulante.
 *
 * Un `<select>` natif plutôt qu'un composant sur mesure : aucune dépendance
 * supplémentaire et le sélecteur natif du système reste bien plus confortable
 * sur mobile (spec 06 §1).
 */
export function SelectField({
  label,
  options,
  registration,
  error,
  hint,
  placeholder,
  className,
  ...props
}: SelectFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        className={cn(
          'border-input bg-background h-11 w-full rounded-md border px-3 text-base shadow-xs outline-none',
          'focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]',
          'aria-invalid:border-destructive disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...registration}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
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
