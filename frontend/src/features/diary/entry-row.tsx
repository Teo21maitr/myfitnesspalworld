import { ArrowRightLeft, Check, CopyPlus, Pencil, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { DiaryEntry } from '@/lib/api/types'

import { useDeleteEntry, useDuplicateEntry, useMealTypes, useUpdateEntry } from './use-diary'

/** Quantité affichée sans décimales inutiles : « 150 g » plutôt que « 150,000 g ». */
function formatQuantity(quantity: string): string {
  return String(Math.round(Number(quantity) * 100) / 100).replace('.', ',')
}

/**
 * Une entrée du journal.
 *
 * Les actions passent par des boutons explicites : un geste ne doit jamais
 * être l'unique moyen d'agir (spec 06 §6).
 */
export function EntryRow({ entry }: { entry: DiaryEntry }) {
  const [editing, setEditing] = useState(false)
  const [moving, setMoving] = useState(false)
  const [quantity, setQuantity] = useState(formatQuantity(entry.quantity))
  const update = useUpdateEntry()
  const remove = useDeleteEntry()
  const duplicate = useDuplicateEntry()
  const mealTypes = useMealTypes()

  const meals = (Array.isArray(mealTypes.data) ? mealTypes.data : []).filter(
    (meal) => meal.is_active && meal.id !== entry.meal_type_id,
  )

  const save = () => {
    const value = Number(quantity.replace(',', '.'))
    if (!(value > 0)) return

    update.mutate(
      { id: entry.id, quantity: String(value) },
      {
        onSuccess: () => {
          toast.success('Quantité mise à jour.')
          setEditing(false)
        },
      },
    )
  }

  return (
    <li className="flex items-center gap-2 border-b py-2 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="flex items-baseline gap-2">
          {entry.food ? (
            <Link to={`/aliments/${entry.food}`} className="truncate font-medium hover:underline">
              {entry.snapshot_name}
            </Link>
          ) : (
            <span className="truncate font-medium">{entry.snapshot_name}</span>
          )}
          {entry.snapshot_brand && (
            <span className="text-muted-foreground truncate text-xs">{entry.snapshot_brand}</span>
          )}
        </p>

        {moving && !editing && (
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="text-muted-foreground text-xs">Déplacer vers :</span>
            {meals.map((meal) => (
              <Button
                key={meal.id}
                type="button"
                size="sm"
                variant="outline"
                className="h-7"
                onClick={() =>
                  update.mutate(
                    { id: entry.id, meal_type_id: meal.id },
                    {
                      onSuccess: () => {
                        toast.success(`Déplacé vers ${meal.name}.`)
                        setMoving(false)
                      },
                    },
                  )
                }
              >
                {meal.name}
              </Button>
            ))}
          </div>
        )}

        {editing ? (
          <div className="mt-1 flex items-center gap-2">
            <Input
              aria-label={`Quantité de ${entry.snapshot_name}`}
              inputMode="decimal"
              className="h-8 w-24"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
            <span className="text-muted-foreground text-xs">{entry.unit_label}</span>
            <Button type="button" size="icon" variant="ghost" onClick={save} aria-label="Valider">
              <Check aria-hidden="true" className="size-4" />
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => {
                setQuantity(formatQuantity(entry.quantity))
                setEditing(false)
              }}
              aria-label="Annuler"
            >
              <X aria-hidden="true" className="size-4" />
            </Button>
          </div>
        ) : (
          <p className="text-muted-foreground text-xs">
            {formatQuantity(entry.quantity)} {entry.unit_label}
          </p>
        )}
      </div>

      <NutrientValue value={entry.computed.energy_kcal} unit="kcal" className="text-sm" />

      {!editing && (
        <>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setEditing(true)}
            aria-label={`Modifier ${entry.snapshot_name}`}
          >
            <Pencil aria-hidden="true" className="size-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            disabled={duplicate.isPending}
            onClick={() =>
              duplicate.mutate(
                { id: entry.id },
                { onSuccess: () => toast.success('Entrée dupliquée.') },
              )
            }
            aria-label={`Dupliquer ${entry.snapshot_name}`}
          >
            <CopyPlus aria-hidden="true" className="size-4" />
          </Button>
          {meals.length > 0 && (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setMoving((value) => !value)}
              aria-label={`Déplacer ${entry.snapshot_name}`}
              aria-expanded={moving}
            >
              <ArrowRightLeft aria-hidden="true" className="size-4" />
            </Button>
          )}
          <Button
            type="button"
            size="icon"
            variant="ghost"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(entry.id, { onSuccess: () => toast.success('Entrée supprimée.') })
            }
            aria-label={`Supprimer ${entry.snapshot_name}`}
          >
            <Trash2 aria-hidden="true" className="size-4" />
          </Button>
        </>
      )}
    </li>
  )
}
