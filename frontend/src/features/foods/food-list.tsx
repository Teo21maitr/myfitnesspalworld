import { TriangleAlert } from 'lucide-react'

import { describeError } from '@/lib/query-client'
import type { FoodListItem } from '@/lib/api/types'

import { FoodRow } from './food-row'

interface FoodListProps {
  foods: FoodListItem[] | undefined
  isPending: boolean
  error: unknown
  emptyMessage: string
}

/** Liste d'aliments et ses états obligatoires (spec 06 §11). */
export function FoodList({ foods, isPending, error, emptyMessage }: FoodListProps) {
  if (isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-2 py-2">
        {[0, 1, 2].map((row) => (
          <div key={row} className="bg-muted h-12 animate-pulse rounded" />
        ))}
        <span className="sr-only">Chargement des aliments…</span>
      </div>
    )
  }

  if (error) {
    return (
      <p role="alert" className="text-destructive flex items-start gap-2 py-4 text-sm">
        <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        {describeError(error)}
      </p>
    )
  }

  if (!foods || foods.length === 0) {
    return <p className="text-muted-foreground py-4 text-sm">{emptyMessage}</p>
  }

  return (
    <ul className="flex flex-col">
      {foods.map((food) => (
        <FoodRow key={food.id} food={food} />
      ))}
    </ul>
  )
}
