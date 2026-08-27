import { Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { ShoppingListItem } from '@/lib/api/types'
import { cn } from '@/lib/utils'

import { useDeleteShoppingItem, useUpdateShoppingItem } from './use-shopping'

function formatQuantity(item: ShoppingListItem): string | null {
  if (item.quantity === null) return null

  const value = Number(item.quantity).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
  return item.unit_label ? `${value} ${item.unit_label}` : value
}

/**
 * Ligne d'article.
 *
 * Cocher est une écriture : sur une liste reçue, ni case ni action. Un article
 * coché reste à sa place, barré — le déplacer ferait sauter la ligne sous le
 * doigt au moment où on la touche.
 */
export function ItemRow({
  listId,
  item,
  editable,
}: {
  listId: number
  item: ShoppingListItem
  editable: boolean
}) {
  const update = useUpdateShoppingItem(listId)
  const remove = useDeleteShoppingItem(listId)

  const [quantity, setQuantity] = useState(item.quantity ?? '')
  const [editing, setEditing] = useState(false)

  // La case répond au doigt, sans attendre l'aller-retour serveur. La donnée
  // reprend la main dès qu'elle change, et l'échec la remet comme elle était.
  const [checked, setChecked] = useState(item.is_checked)
  const [syncedWith, setSyncedWith] = useState(item.is_checked)

  if (syncedWith !== item.is_checked) {
    setSyncedWith(item.is_checked)
    setChecked(item.is_checked)
  }

  const amount = formatQuantity(item)

  const saveQuantity = () => {
    setEditing(false)
    const parsed = quantity.trim() === '' ? null : String(Number(quantity.replace(',', '.')))
    if (parsed === (item.quantity ?? null)) return

    update.mutate({ itemId: item.id, quantity: parsed })
  }

  return (
    <li className="flex items-center gap-3 border-b py-2 last:border-b-0">
      {editable && (
        <input
          type="checkbox"
          className="size-4 shrink-0"
          checked={checked}
          aria-label={`Marquer ${item.name} comme acheté`}
          onChange={(event) => {
            const next = event.target.checked
            setChecked(next)
            update.mutate(
              { itemId: item.id, is_checked: next },
              { onError: () => setChecked(!next) },
            )
          }}
        />
      )}

      <span
        className={cn('flex-1 text-sm', item.is_checked && 'text-muted-foreground line-through')}
      >
        {item.name}
      </span>

      {editable && editing ? (
        <Input
          autoFocus
          inputMode="decimal"
          className="h-9 w-24"
          aria-label={`Quantité de ${item.name}`}
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          onBlur={saveQuantity}
          onKeyDown={(event) => event.key === 'Enter' && saveQuantity()}
        />
      ) : (
        <button
          type="button"
          disabled={!editable}
          onClick={() => setEditing(true)}
          className={cn(
            'text-muted-foreground text-sm',
            editable && 'hover:text-foreground rounded px-1',
          )}
        >
          {amount ?? '—'}
        </button>
      )}

      {editable && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Retirer ${item.name}`}
          disabled={remove.isPending}
          onClick={() => remove.mutate(item.id)}
        >
          {remove.isPending ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <Trash2 aria-hidden="true" className="size-4" />
          )}
        </Button>
      )}
    </li>
  )
}
