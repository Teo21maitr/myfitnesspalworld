import type { FoodNutrition } from '@/lib/api/types'

import { NutrientValue } from './nutrient-value'

interface Row {
  label: string
  key: keyof FoodNutrition
  unit: string
}

const MACROS: Row[] = [
  { label: 'Énergie', key: 'energy_kcal', unit: 'kcal' },
  { label: 'Protéines', key: 'protein_g', unit: 'g' },
  { label: 'Glucides', key: 'carbohydrates_g', unit: 'g' },
  { label: 'dont sucres', key: 'sugars_g', unit: 'g' },
  { label: 'Lipides', key: 'fat_g', unit: 'g' },
  { label: 'Fibres', key: 'fiber_g', unit: 'g' },
  { label: 'Glucides nets', key: 'net_carbs_g', unit: 'g' },
]

const MICROS: Row[] = [
  { label: 'Sel', key: 'salt_g', unit: 'g' },
  { label: 'Sodium', key: 'sodium_mg', unit: 'mg' },
  { label: 'Cholestérol', key: 'cholesterol_mg', unit: 'mg' },
  { label: 'Potassium', key: 'potassium_mg', unit: 'mg' },
  { label: 'Calcium', key: 'calcium_mg', unit: 'mg' },
  { label: 'Fer', key: 'iron_mg', unit: 'mg' },
  { label: 'Magnésium', key: 'magnesium_mg', unit: 'mg' },
  { label: 'Vitamine A', key: 'vitamin_a_ug', unit: 'µg' },
  { label: 'Vitamine B6', key: 'vitamin_b6_mg', unit: 'mg' },
  { label: 'Vitamine B12', key: 'vitamin_b12_ug', unit: 'µg' },
  { label: 'Vitamine C', key: 'vitamin_c_mg', unit: 'mg' },
  { label: 'Vitamine D', key: 'vitamin_d_ug', unit: 'µg' },
  { label: 'Vitamine E', key: 'vitamin_e_mg', unit: 'mg' },
  { label: 'Vitamine K', key: 'vitamin_k_ug', unit: 'µg' },
]

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
