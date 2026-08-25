import { Check } from 'lucide-react'

import { cn } from '@/lib/utils'

import { STEPS } from './schema'

/** Indicateur de progression du parcours d'onboarding. */
export function Stepper({ currentIndex }: { currentIndex: number }) {
  const current = STEPS[currentIndex]

  return (
    <div className="flex flex-col gap-2">
      <p className="text-muted-foreground text-sm">
        Étape {currentIndex + 1} sur {STEPS.length} — {current?.title}
      </p>

      <ol className="flex items-center gap-1.5" aria-label="Progression de l’onboarding">
        {STEPS.map((step, index) => {
          const done = index < currentIndex
          const active = index === currentIndex

          return (
            <li key={step.id} className="flex-1">
              <div
                aria-current={active ? 'step' : undefined}
                className={cn(
                  'flex h-1.5 items-center justify-center rounded-full',
                  done || active ? 'bg-primary' : 'bg-muted',
                )}
              >
                <span className="sr-only">
                  {step.title}
                  {done ? ' (terminée)' : active ? ' (en cours)' : ''}
                </span>
              </div>
            </li>
          )
        })}
      </ol>

      {currentIndex === STEPS.length - 1 && (
        <p className="text-success flex items-center gap-1.5 text-xs">
          <Check aria-hidden="true" className="size-3.5" />
          Dernière étape
        </p>
      )}
    </div>
  )
}
