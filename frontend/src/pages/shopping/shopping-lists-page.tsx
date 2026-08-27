import { Loader2, Plus, ShoppingCart, TriangleAlert } from 'lucide-react'
import { useId, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { GenerateForm } from '@/features/shopping/generate-form'
import { useCreateShoppingList, useShoppingLists } from '@/features/shopping/use-shopping'
import { describeError } from '@/lib/query-client'

/** Listes de courses (spec 01 §16). */
export function ShoppingListsPage() {
  const navigate = useNavigate()
  const nameId = useId()
  const [name, setName] = useState('')

  const { data, error, isPending } = useShoppingLists()
  const create = useCreateShoppingList()

  const lists = Array.isArray(data?.results) ? data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Courses</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Générées depuis vos recettes ou vos journées, avec les quantités regroupées.
        </p>
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <div className="bg-muted h-24 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement des listes…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {data && lists.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="text-base">
              <ShoppingCart aria-hidden="true" className="mr-2 inline size-4" />
              Aucune liste
            </CardTitle>
            <CardDescription>
              Générez-en une depuis une recette : les mêmes ingrédients se regroupent en une seule
              ligne, quantités converties.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {lists.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <ul className="flex flex-col">
              {lists.map((list) => (
                <li key={list.id} className="border-b last:border-b-0">
                  <Link
                    to={`/courses/${list.id}`}
                    className="hover:bg-accent -mx-2 flex flex-col gap-0.5 rounded-md px-2 py-3"
                  >
                    <span className="font-medium">{list.name}</span>
                    <span className="text-muted-foreground text-xs">
                      {list.items.length} article{list.items.length > 1 ? 's' : ''}
                      {!list.is_editable && ' · partagée avec vous'}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Générer une liste
          </CardTitle>
        </CardHeader>
        <CardContent>
          <GenerateForm onDone={(id) => void navigate(`/courses/${id}`)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Liste vide
          </CardTitle>
          <CardDescription>Pour la remplir à la main.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              if (name.trim() === '') return
              create.mutate(
                { name: name.trim() },
                {
                  onSuccess: (list) => {
                    toast.success('Liste créée.')
                    setName('')
                    void navigate(`/courses/${list.id}`)
                  },
                },
              )
            }}
          >
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor={nameId}>Nom</Label>
              <Input
                id={nameId}
                value={name}
                placeholder="Courses du samedi"
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <Button type="submit" disabled={create.isPending || name.trim() === ''}>
              {create.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
              <Plus aria-hidden="true" className="size-4" />
              Créer
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
