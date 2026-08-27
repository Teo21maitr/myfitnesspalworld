import { ArrowLeft, Loader2, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { useId, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ShareDialog } from '@/features/shares/share-dialog'
import { ItemRow } from '@/features/shopping/item-row'
import {
  useAddShoppingItem,
  useDeleteShoppingList,
  useShoppingList,
} from '@/features/shopping/use-shopping'
import { describeError } from '@/lib/query-client'

/** Détail d'une liste : les articles, cochables si elle est à nous. */
export function ShoppingListPage() {
  const params = useParams()
  const navigate = useNavigate()
  const id = Number(params.id)
  const nameId = useId()
  const quantityId = useId()

  const { data: list, error, isPending } = useShoppingList(id)
  const addItem = useAddShoppingItem(id)
  const removeList = useDeleteShoppingList()

  const [name, setName] = useState('')
  const [quantity, setQuantity] = useState('')

  const isUnknown = !Number.isFinite(id)

  if (isPending && !isUnknown) {
    return (
      <div aria-busy="true" className="mx-auto w-full max-w-2xl">
        <div className="bg-muted h-40 animate-pulse rounded-xl" />
        <span className="sr-only">Chargement de la liste…</span>
      </div>
    )
  }

  if (error || isUnknown || !list) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error ? describeError(error) : 'Liste introuvable.'}
        </p>
      </div>
    )
  }

  const remaining = list.items.filter((item) => !item.is_checked).length

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/courses">
            <ArrowLeft aria-hidden="true" />
            Courses
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">{list.name}</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {remaining} article{remaining > 1 ? 's' : ''} à acheter
          {!list.is_editable && ' · consultation seule'}
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          {list.items.length === 0 ? (
            <p className="text-muted-foreground text-sm">Cette liste est vide.</p>
          ) : (
            <ul className="flex flex-col">
              {list.items.map((item) => (
                <ItemRow key={item.id} listId={list.id} item={item} editable={list.is_editable} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {list.is_editable && (
        <>
          <Card>
            <CardHeader>
              <CardTitle as="h2" className="text-base">
                Ajouter un article
              </CardTitle>
              <CardDescription>La quantité est facultative.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="flex items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  if (name.trim() === '') return
                  addItem.mutate(
                    {
                      name: name.trim(),
                      quantity:
                        quantity.trim() === '' ? null : String(Number(quantity.replace(',', '.'))),
                    },
                    {
                      onSuccess: () => {
                        setName('')
                        setQuantity('')
                      },
                    },
                  )
                }}
              >
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label htmlFor={nameId}>Article</Label>
                  <Input
                    id={nameId}
                    value={name}
                    placeholder="Sel"
                    onChange={(event) => setName(event.target.value)}
                  />
                </div>
                <div className="flex w-24 flex-col gap-1.5">
                  <Label htmlFor={quantityId}>Quantité</Label>
                  <Input
                    id={quantityId}
                    inputMode="decimal"
                    value={quantity}
                    onChange={(event) => setQuantity(event.target.value)}
                  />
                </div>
                <Button type="submit" disabled={addItem.isPending || name.trim() === ''}>
                  {addItem.isPending && (
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                  )}
                  <Plus aria-hidden="true" className="size-4" />
                  Ajouter
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="flex flex-wrap gap-2">
            <ShareDialog resourceType="shopping_list" resourceId={list.id} label={list.name} />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-destructive"
              disabled={removeList.isPending}
              onClick={() =>
                removeList.mutate(list.id, {
                  onSuccess: () => {
                    toast.success('Liste supprimée.')
                    void navigate('/courses')
                  },
                })
              }
            >
              <Trash2 aria-hidden="true" className="size-4" />
              Supprimer la liste
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
