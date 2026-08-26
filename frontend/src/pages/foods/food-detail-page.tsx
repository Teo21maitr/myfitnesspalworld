import { ArrowLeft, Star, TriangleAlert } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AddToDiaryForm } from '@/features/diary/add-to-diary-form'
import { NutritionTable } from '@/features/foods/nutrition-table'
import { PortionEditor } from '@/features/foods/portion-editor'
import { useFood, useToggleFavorite } from '@/features/foods/use-foods'
import { describeError } from '@/lib/query-client'
import { cn } from '@/lib/utils'

export function FoodDetailPage() {
  const { id } = useParams()
  const foodId = Number(id)
  const { data: food, error, isPending } = useFood(foodId)
  const toggleFavorite = useToggleFavorite()

  if (isPending) {
    return (
      <div aria-busy="true" className="mx-auto flex w-full max-w-2xl flex-col gap-3">
        <div className="bg-muted h-8 w-56 animate-pulse rounded" />
        <div className="bg-muted h-48 animate-pulse rounded-xl" />
        <span className="sr-only">Chargement de l’aliment…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
        <Button asChild variant="outline" className="self-start">
          <Link to="/aliments">Retour à la recherche</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/aliments">
            <ArrowLeft aria-hidden="true" />
            Aliments
          </Link>
        </Button>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{food.name}</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              {food.brand && <span>{food.brand} · </span>}
              {/* La source de la donnée reste affichée (spec 01 §8). */}
              <span>Source : {food.source_label}</span>
              {food.is_verified && <span> · fiche vérifiée</span>}
            </p>
          </div>

          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={food.is_favorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
            aria-pressed={food.is_favorite}
            onClick={() => toggleFavorite.mutate({ id: food.id, isFavorite: food.is_favorite })}
          >
            <Star
              aria-hidden="true"
              className={cn(food.is_favorite && 'fill-warning text-warning')}
            />
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Ajouter au journal</CardTitle>
          <CardDescription>
            Choisissez la quantité, le repas et la date. Seules les unités calculables pour cet
            aliment sont proposées.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AddToDiaryForm food={food} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Valeurs nutritionnelles</CardTitle>
          <CardDescription>
            Pour {Math.round(Number(food.reference_amount))} {food.reference_unit}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {food.nutrition ? (
            <NutritionTable nutrition={food.nutrition} />
          ) : (
            <p className="text-muted-foreground text-sm">
              Aucune valeur nutritionnelle enregistrée.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Portions</CardTitle>
          <CardDescription>Des quantités pratiques pour la saisie.</CardDescription>
        </CardHeader>
        <CardContent>
          <PortionEditor food={food} />
        </CardContent>
      </Card>

      {food.is_editable && (
        <Button asChild variant="outline" className="self-start">
          <Link to={`/mes-aliments/${food.id}`}>Modifier cet aliment</Link>
        </Button>
      )}
    </div>
  )
}
