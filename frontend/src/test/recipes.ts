import type { RecipeDetail, RecipeListItem, RecipeNutrition, SavedMeal } from '@/lib/api/types'
import { jsonResponse } from '@/test/fetch-mock'

export const TEST_USER = {
  id: 1,
  username: 'teo',
  first_name: 'Téo',
  last_name: 'Maitrot',
  email: null,
  status: 'ACTIVE',
  is_staff: false,
  onboarding_completed: true,
}

const NUTRIENTS = [
  'energy_kcal',
  'protein_g',
  'carbohydrates_g',
  'fat_g',
  'fiber_g',
  'sugars_g',
  'sodium_mg',
  'salt_g',
  'cholesterol_mg',
  'potassium_mg',
  'calcium_mg',
  'iron_mg',
  'magnesium_mg',
  'vitamin_a_ug',
  'vitamin_b6_mg',
  'vitamin_b12_ug',
  'vitamin_c_mg',
  'vitamin_d_ug',
  'vitamin_e_mg',
  'vitamin_k_ug',
] as const

export function recipeNutrition(
  values: Partial<RecipeNutrition> = {},
  incomplete: string[] = [],
): RecipeNutrition {
  return {
    // `fromEntries` perd la forme du type : le double passage est nécessaire.
    ...(Object.fromEntries(
      NUTRIENTS.map((key) => [key, values[key] ?? null]),
    ) as unknown as RecipeNutrition),
    net_carbs_g: null,
    incomplete_nutrients: incomplete,
  }
}

export function recipeListItem(overrides: Partial<RecipeListItem> = {}): RecipeListItem {
  return {
    id: 3,
    name: 'Poulet rôti',
    description: '',
    servings: '2.00',
    visibility: 'private',
    is_favorite: false,
    nutrition: recipeNutrition({ energy_kcal: '350.000' }),
    ingredient_count: 2,
    is_editable: true,
    created_at: '2026-08-26T08:00:00Z',
    updated_at: '2026-08-26T08:00:00Z',
    ...overrides,
  }
}

export function recipeDetail(overrides: Partial<RecipeDetail> = {}): RecipeDetail {
  return {
    ...recipeListItem(),
    instructions: 'Faire revenir.',
    ingredients: [
      { id: 1, food: 7, food_name: 'Poulet', quantity: '200.000', unit_label: 'g', sort_order: 0 },
    ],
    ...overrides,
  }
}

export function savedMeal(overrides: Partial<SavedMeal> = {}): SavedMeal {
  return {
    id: 9,
    name: 'Mon déjeuner',
    description: '',
    visibility: 'private',
    items: [
      {
        id: 1,
        item_type: 'food',
        food: 7,
        recipe: null,
        item_name: 'Poulet',
        quantity: '150.000',
        unit_label: 'g',
        sort_order: 0,
      },
    ],
    is_editable: true,
    created_at: '2026-08-26T08:00:00Z',
    updated_at: '2026-08-26T08:00:00Z',
    ...overrides,
  }
}

export function paginated(rows: unknown[]) {
  return { count: rows.length, next: null, previous: null, results: rows }
}

export const MEAL_TYPES = [
  {
    id: 1,
    name: 'Petit-déjeuner',
    slug: 'petit-dejeuner',
    sort_order: 0,
    is_active: true,
    is_system: true,
    system_key: 'breakfast',
  },
]

/** Routes communes à tous les écrans authentifiés. */
export const BASE_ROUTES = [
  { match: '/auth/me/', respond: () => jsonResponse(TEST_USER) },
  {
    match: '/profile/settings/',
    respond: () =>
      jsonResponse({
        language: 'fr',
        theme_mode: 'system',
        date_format: 'DD/MM/YYYY',
        food_search_languages: ['fr', 'en'],
        available_food_search_languages: [
          { code: 'de', label: 'Allemand' },
          { code: 'en', label: 'Anglais' },
          { code: 'fr', label: 'Français' },
          { code: 'sv', label: 'Suédois' },
        ],
      }),
  },
  { match: '/meal-types/', respond: () => jsonResponse(MEAL_TYPES) },
]
