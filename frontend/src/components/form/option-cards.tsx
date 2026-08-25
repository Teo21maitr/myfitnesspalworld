import { useId } from 'react'
import type { FieldError } from 'react-hook-form'

import { cn } from '@/lib/utils'

export interface CardOption<T extends string> {
  value: T
  label: string
  description?: string
}

interface OptionCardsProps<T extends string> {
  legend: string
  options: readonly CardOption<T>[]
  value: T | undefined
  onChange: (value: T) => void
  error?: FieldError
  name: string
}

/**
 * Groupe de boutons radio présentés en cartes.
 *
 * Les cartes sont de vrais `<input type="radio">` : la navigation clavier et
 * les lecteurs d'écran fonctionnent nativement (spec 06 §12).
 */
export function OptionCards<T extends string>({
  legend,
  options,
  value,
  onChange,
  error,
  name,
}: OptionCardsProps<T>) {
  const id = useId()
  const errorId = `${id}-error`

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm leading-none font-medium">{legend}</legend>

      <div className="flex flex-col gap-2">
        {options.map((option) => {
          const selected = value === option.value
          return (
            <label
              key={option.value}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors',
                'has-[:focus-visible]:ring-ring/50 has-[:focus-visible]:ring-[3px]',
                selected ? 'border-primary bg-primary/5' : 'hover:bg-accent',
              )}
            >
              <input
                type="radio"
                name={name}
                value={option.value}
                checked={selected}
                onChange={() => onChange(option.value)}
                className="accent-primary mt-1 size-4"
                aria-describedby={error ? errorId : undefined}
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">{option.label}</span>
                {option.description && (
                  <span className="text-muted-foreground text-xs">{option.description}</span>
                )}
              </span>
            </label>
          )
        })}
      </div>

      {error && (
        <p id={errorId} role="alert" className="text-destructive text-xs">
          {error.message}
        </p>
      )}
    </fieldset>
  )
}
