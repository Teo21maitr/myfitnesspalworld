import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useId, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { describeError } from '@/lib/query-client'
import type { FoodDetail } from '@/lib/api/types'

import { addPortion, deletePortion, foodDetailQueryKey } from './api'

/**
 * Portions d'un aliment (spec 01 §9).
 *
 * Une portion ajoutée sur un aliment global reste privée à son créateur, ce
 * que l'interface signale explicitement.
 */
export function PortionEditor({ food }: { food: FoodDetail }) {
  const queryClient = useQueryClient()
  const nameId = useId()
  const gramsId = useId()

  const [name, setName] = useState('')
  const [grams, setGrams] = useState('')

  const invalidate = () => queryClient.invalidateQueries({ queryKey: foodDetailQueryKey(food.id) })

  const create = useMutation({
    mutationFn: () => addPortion(food.id, { name, gram_equivalent: grams }),
    onSuccess: () => {
      setName('')
      setGrams('')
      toast.success('Portion ajoutée.')
      invalidate()
    },
    onError: (error) => toast.error(describeError(error)),
  })

  const remove = useMutation({
    mutationFn: (portionId: number) => deletePortion(food.id, portionId),
    onSuccess: () => {
      toast.success('Portion supprimée.')
      invalidate()
    },
    onError: (error) => toast.error(describeError(error)),
  })

  return (
    <div className="flex flex-col gap-4">
      {food.portions.length > 0 ? (
        <ul className="flex flex-col">
          {food.portions.map((portion) => (
            <li
              key={portion.id}
              className="flex items-center justify-between gap-3 border-b py-2 last:border-b-0"
            >
              <span className="flex flex-col">
                <span className="text-sm font-medium">{portion.name}</span>
                <span className="text-muted-foreground text-xs">
                  {portion.gram_equivalent
                    ? `${Math.round(Number(portion.gram_equivalent))} g`
                    : portion.milliliter_equivalent
                      ? `${Math.round(Number(portion.milliliter_equivalent))} ml`
                      : `${Math.round(Number(portion.unit_equivalent))} unité(s)`}
                  {portion.is_own && ' · portion personnelle'}
                </span>
              </span>

              {portion.is_own && (
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Supprimer la portion ${portion.name}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(portion.id)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-sm">Aucune portion enregistrée.</p>
      )}

      <form
        noValidate
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor={nameId}>Nom de la portion</Label>
          <Input
            id={nameId}
            value={name}
            placeholder="1 tranche"
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <div className="flex w-full flex-col gap-1.5 sm:w-32">
          <Label htmlFor={gramsId}>Grammes</Label>
          <Input
            id={gramsId}
            type="number"
            inputMode="decimal"
            value={grams}
            placeholder="32"
            onChange={(event) => setGrams(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={!name || !grams || create.isPending}>
          Ajouter
        </Button>
      </form>

      <p className="text-muted-foreground text-xs">
        Une portion que vous ajoutez sur un aliment partagé n’est visible que par vous.
      </p>
    </div>
  )
}
