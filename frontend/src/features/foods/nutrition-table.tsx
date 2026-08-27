import type { FoodNutrition } from '@/lib/api/types'

import { NutrientValue } from './nutrient-value'
import { MACROS, MICROS, type Row } from './nutrients'

function Section({
  title,
  rows,
  nutrition,
}: {
  title: string
  rows: Row[]
  nutrition: FoodNutrition
}) {
  return (
    <section>
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      <dl>
        {rows.map((row) => (
          <div
            key={row.key}
            className="flex items-baseline justify-between gap-4 border-b py-1.5 last:border-b-0"
          >
            <dt className="text-muted-foreground text-sm">{row.label}</dt>
            <dd className="text-sm font-medium">
              <NutrientValue value={nutrition[row.key]} unit={row.unit} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/**
 * Détail nutritionnel d'un aliment.
 *
 * Une valeur non renseignée s'affiche « — » : un produit partiellement
 * renseigné reste parfaitement utilisable (spec 01 §8).
 */
export function NutritionTable({ nutrition }: { nutrition: FoodNutrition }) {
  return (
    <div className="flex flex-col gap-5">
      <Section title="Macronutriments" rows={MACROS} nutrition={nutrition} />
      <Section title="Micronutriments" rows={MICROS} nutrition={nutrition} />
    </div>
  )
}
