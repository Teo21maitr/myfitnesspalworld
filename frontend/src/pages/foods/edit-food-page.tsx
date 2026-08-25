import { ArrowLeft, TriangleAlert } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { FoodForm } from '@/features/foods/food-form'
import { useFood } from '@/features/foods/use-foods'
import { describeError } from '@/lib/query-client'

export function EditFoodPage() {
  const { id } = useParams()
  const { data: food, error, isPending } = useFood(Number(id))

  if (isPending) {
    return (
      <div aria-busy="true" className="mx-auto w-full max-w-2xl">
        <div className="bg-muted h-64 animate-pulse rounded-xl" />
        <span className="sr-only">Chargement de l’aliment…</span>
      </div>
    )
  }

  if (error || !food.is_editable) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error
            ? describeError(error)
            : 'Cet aliment ne vous appartient pas : vous ne pouvez pas le modifier.'}
        </p>
        <Button asChild variant="outline" className="self-start">
          <Link to="/mes-aliments">Retour à mes aliments</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 self-start">
        <Link to={`/aliments/${food.id}`}>
          <ArrowLeft aria-hidden="true" />
          Retour à la fiche
        </Link>
      </Button>

      <Card>
        <CardHeader>
          <CardTitle as="h1">Modifier {food.name}</CardTitle>
        </CardHeader>
        <CardContent>
          <FoodForm food={food} />
        </CardContent>
      </Card>
    </div>
  )
}
