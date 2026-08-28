import { Plus, ScanText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
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
  // Un scan infructueux mène ici avec le code déjà connu : le formulaire
  // s'ouvre prérempli plutôt que de faire recopier le code (spec 01 §10).
  const [searchParams] = useSearchParams()
  const prefilledBarcode = searchParams.get('barcode') ?? undefined
  const [creating, setCreating] = useState(searchParams.get('creer') === '1')

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
          <div className="flex shrink-0 gap-2">
            {/* Saisir quinze champs à la main quand l'étiquette est sous les
                yeux n'a pas de sens : c'est ici qu'on vient créer un aliment,
                donc c'est ici que le raccourci doit être. */}
            <Button asChild type="button" size="sm" variant="outline">
              <Link to="/scanner-etiquette">
                <ScanText aria-hidden="true" />
                Depuis l’étiquette
              </Link>
            </Button>
            <Button type="button" size="sm" onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" />
              Créer
            </Button>
          </div>
        )}
      </div>

      {creating && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Nouvel aliment</CardTitle>
            <CardDescription>
              {prefilledBarcode
                ? `Code-barres ${prefilledBarcode}, introuvable dans les sources connues.`
                : 'Les valeurs portent sur la quantité de référence indiquée.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <FoodForm barcode={prefilledBarcode} />
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
