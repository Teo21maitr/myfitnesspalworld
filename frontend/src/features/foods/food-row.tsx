import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { FoodListItem } from '@/lib/api/types'
import { cn } from '@/lib/utils'

import { NutrientValue } from './nutrient-value'
import { useToggleFavorite } from './use-foods'

/** Ligne de résultat de recherche (spec 06 §7). */
export function FoodRow({ food }: { food: FoodListItem }) {
  const toggleFavorite = useToggleFavorite()

  return (
    <li className="flex items-center gap-2 border-b last:border-b-0">
      <Link
        to={`/aliments/${food.id}`}
        className="hover:bg-accent -mx-2 flex flex-1 flex-col gap-0.5 rounded-md px-2 py-3"
      >
        <span className="flex items-baseline gap-2">
          <span className="font-medium">{food.name}</span>
          {food.brand && <span className="text-muted-foreground text-sm">{food.brand}</span>}
        </span>
        <span className="text-muted-foreground flex items-center gap-2 text-xs">
          <NutrientValue value={food.energy_kcal} unit="kcal" />
          <span aria-hidden="true">·</span>
          <span>
            pour {Math.round(Number(food.reference_amount))} {food.reference_unit}
          </span>
          <span aria-hidden="true">·</span>
          {/* La source reste visible mais discrète (spec 01 §8). */}
          <span>{food.source_label}</span>
        </span>
      </Link>

      <Button
        type="button"
        size="icon"
        variant="ghost"
        aria-label={
          food.is_favorite ? `Retirer ${food.name} des favoris` : `Ajouter ${food.name} aux favoris`
        }
        aria-pressed={food.is_favorite}
        onClick={() => toggleFavorite.mutate({ id: food.id, isFavorite: food.is_favorite })}
      >
        <Star aria-hidden="true" className={cn(food.is_favorite && 'fill-warning text-warning')} />
      </Button>
    </li>
  )
}
