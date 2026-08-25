import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FoodForm } from '@/features/foods/food-form'
import { NutrientValue } from '@/features/foods/nutrient-value'
import { useDeleteFood, useMyFoods } from '@/features/foods/use-foods'
import { describeError } from '@/lib/query-client'

export function MyFoodsPage() {
  const { data, error, isPending } = useMyFoods()
  const remove = useDeleteFood()
  const [creating, setCreating] = useState(false)

  const foods = data?.results ?? []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Mes aliments</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Vos aliments personnels, privés par défaut.
          </p>
        </div>
        {!creating && (
          <Button type="button" size="sm" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
            Créer
          </Button>
        )}
      </div>

      {creating && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Nouvel aliment</CardTitle>
            <CardDescription>
              Les valeurs portent sur la quantité de référence indiquée.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <FoodForm />
            <Button
              type="button"
              variant="ghost"
              className="self-start"
              onClick={() => setCreating(false)}
            >
              Annuler
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle as="h2">Mes créations</CardTitle>
        </CardHeader>
        <CardContent>
          {isPending && (
            <div aria-busy="true" className="flex flex-col gap-2">
              <div className="bg-muted h-12 animate-pulse rounded" />
              <span className="sr-only">Chargement de vos aliments…</span>
            </div>
          )}

          {error && (
            <p role="alert" className="text-destructive text-sm">
              {describeError(error)}
            </p>
          )}

          {!isPending && !error && foods.length === 0 && (
            <p className="text-muted-foreground text-sm">Vous n’avez pas encore créé d’aliment.</p>
          )}

          {foods.length > 0 && (
            <ul className="flex flex-col">
              {foods.map((food) => (
                <li
                  key={food.id}
                  className="flex items-center justify-between gap-3 border-b py-2 last:border-b-0"
                >
                  <Link
                    to={`/aliments/${food.id}`}
                    className="flex flex-1 flex-col hover:underline"
                  >
                    <span className="text-sm font-medium">{food.name}</span>
                    <span className="text-muted-foreground text-xs">
                      <NutrientValue value={food.energy_kcal} unit="kcal" /> pour{' '}
                      {Math.round(Number(food.reference_amount))} {food.reference_unit}
                    </span>
                  </Link>

                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    aria-label={`Supprimer ${food.name}`}
                    disabled={remove.isPending}
                    onClick={() =>
                      remove
                        .mutateAsync(food.id)
                        .then(() => toast.success('Aliment supprimé.'))
                        .catch((deleteError: unknown) => toast.error(describeError(deleteError)))
                    }
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
