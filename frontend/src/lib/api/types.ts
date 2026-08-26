/** Format d'erreur normalisé renvoyé par l'API (spec 10 §5). */
export interface ApiErrorPayload {
  code: string
  message: string
  errors: Record<string, string[]>
}

/** Enveloppe de pagination `page` / `limit` (spec 04). */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  version: string
  time: string
  checks: {
    database: 'ok' | 'error'
    cache: 'ok' | 'error'
  }
}

export type AccountStatus = 'PENDING' | 'ACTIVE' | 'SUSPENDED'

export type ThemeMode = 'light' | 'dark' | 'system'

/** Réponse de `GET /auth/me/` — strictement ce dont le frontend a besoin. */
export interface AuthUser {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string | null
  status: AccountStatus
  is_staff: boolean
  onboarding_completed: boolean
}

export type SexForCalculation = 'FEMALE' | 'MALE'

export type ActivityLevel =
  'SEDENTARY' | 'LIGHTLY_ACTIVE' | 'MODERATELY_ACTIVE' | 'VERY_ACTIVE' | 'EXTREMELY_ACTIVE'

export type GoalType = 'LOSS' | 'MAINTENANCE' | 'GAIN'

export type MacroMode = 'percentage' | 'grams'

/** Origine d'une valeur : calculée par l'application ou saisie. */
export type ValueSource = 'calculated' | 'manual'

/**
 * Données nutritionnelles du profil.
 *
 * Les décimales transitent en chaînes de caractères : DRF sérialise ainsi les
 * `DecimalField`, ce qui évite toute perte de précision en flottant.
 */
export interface NutritionProfile {
  birth_date: string | null
  sex_for_calculation: SexForCalculation | null
  height_cm: string | null
  activity_level: ActivityLevel | null
  goal_type: GoalType | null
  goal_rate_kg_per_week: string | null
  target_weight_kg: string | null
  onboarding_completed: boolean
}

/** Réponse de `GET /profile/`. */
export interface Profile extends AuthUser {
  created_at: string
  profile: NutritionProfile
}

/** Résultat de `POST /profile/goals/calculate/`. */
export interface CalorieEstimate {
  bmr: string
  tdee: string
  daily_calories: string
  protein_g: string
  carbs_g: string
  fat_g: string
  warnings: string[]
  notice: string
}

/** Surcharge d'objectif pour un jour de la semaine (0 = lundi). */
export interface DayOverride {
  id: number
  weekday: number
  weekday_label: string
  daily_calories: string | null
  protein_g: string | null
  carbs_g: string | null
  fat_g: string | null
  fiber_g: string | null
  enabled: boolean
}

export interface NutritionGoal {
  id: number
  daily_calories: string
  protein_g: string
  carbs_g: string
  fat_g: string
  fiber_g: string | null
  net_carbs_g: string | null
  macro_mode: MacroMode
  calories_source: ValueSource
  macros_source: ValueSource
  start_date: string
  end_date: string | null
  is_current: boolean
  /** Écart entre les calories visées et celles impliquées par les macros. */
  macro_calories_gap: string
  day_overrides: DayOverride[]
  created_at: string
}

/** Réponse de `GET /profile/goals/current/`. */
export interface CurrentGoal {
  goal: NutritionGoal
  today: {
    date: string
    weekday: number
    daily_calories: string
    protein_g: string
    carbs_g: string
    fat_g: string
    fiber_g: string | null
  }
}

export interface WeightEntry {
  id: number
  date: string
  weight_kg: string
  notes: string | null
  created_at: string
  updated_at: string
}

/** Réponse de `GET /profile/settings/`. */
export interface UserSettings {
  language: string
  theme_mode: ThemeMode
  date_format: string
}

export interface DetailResponse {
  detail: string
}

export type FoodSource = 'ciqual' | 'off' | 'user' | 'generated'

export type FoodVisibility = 'private' | 'specific_users' | 'app_users'

export type UnitType = 'g' | 'ml' | 'unit'

/**
 * Valeurs nutritionnelles pour la quantité de référence.
 *
 * Une valeur absente vaut `null` et doit s'afficher « — », jamais 0
 * (spec 01 §8).
 */
export interface FoodNutrition {
  energy_kcal: string | null
  protein_g: string | null
  carbohydrates_g: string | null
  fat_g: string | null
  fiber_g: string | null
  sugars_g: string | null
  sodium_mg: string | null
  salt_g: string | null
  cholesterol_mg: string | null
  potassium_mg: string | null
  calcium_mg: string | null
  iron_mg: string | null
  magnesium_mg: string | null
  vitamin_a_ug: string | null
  vitamin_b6_mg: string | null
  vitamin_b12_ug: string | null
  vitamin_c_mg: string | null
  vitamin_d_ug: string | null
  vitamin_e_mg: string | null
  vitamin_k_ug: string | null
  net_carbs_g: string | null
}

export interface FoodPortion {
  id: number
  name: string
  gram_equivalent: string | null
  milliliter_equivalent: string | null
  unit_equivalent: string | null
  is_default: boolean
  sort_order: number
  is_own: boolean
}

/** Ligne de résultat de recherche. */
export interface FoodListItem {
  id: number
  name: string
  brand: string
  source: FoodSource
  source_label: string
  reference_amount: string
  reference_unit: UnitType
  energy_kcal: string | null
  is_favorite: boolean
  is_own: boolean
  is_verified: boolean
}

/** Fiche complète d'un aliment. */
export interface FoodDetail extends FoodListItem {
  barcode: string | null
  visibility: FoodVisibility
  default_unit_type: UnitType
  nutrition: FoodNutrition | null
  portions: FoodPortion[]
  /** Unités réellement calculables pour cet aliment (spec 01 §9). */
  available_units: string[]
  is_editable: boolean
  created_at: string
  updated_at: string
}

/**
 * Résultat de recherche Open Food Facts, avant tout enregistrement.
 *
 * Volontairement pauvre : la recherche élargie sert à choisir un produit. Ses
 * valeurs nutritionnelles ne sont chargées qu'ensuite, par le code-barres.
 */
export interface ExternalFoodCandidate {
  code: string
  name: string
  brand: string
  /** Renseigné quand le produit est déjà en base : sa fiche s'ouvre directement. */
  food_id: number | null
}

/** Repas d'une journée (spec 01 §5). */
export interface MealType {
  id: number
  name: string
  slug: string
  sort_order: number
  is_active: boolean
  /** Un repas système se désactive, il ne se supprime pas. */
  is_system: boolean
  system_key: string | null
}

/**
 * Valeurs nutritionnelles, en chaînes décimales.
 *
 * `null` signifie « inconnu » et jamais zéro (spec 01 §8).
 */
export interface NutritionValues {
  energy_kcal: string | null
  protein_g: string | null
  carbohydrates_g: string | null
  fat_g: string | null
  fiber_g: string | null
  sugars_g: string | null
  sodium_mg: string | null
  salt_g: string | null
  cholesterol_mg: string | null
  potassium_mg: string | null
  calcium_mg: string | null
  iron_mg: string | null
  magnesium_mg: string | null
  vitamin_a_ug: string | null
  vitamin_b6_mg: string | null
  vitamin_b12_ug: string | null
  vitamin_c_mg: string | null
  vitamin_d_ug: string | null
  vitamin_e_mg: string | null
  vitamin_k_ug: string | null
}

export type EntryType = 'food' | 'recipe' | 'quick_add'

/** Entrée de journal, avec ses valeurs réellement consommées. */
export interface DiaryEntry {
  id: number
  meal_type_id: number
  entry_type: EntryType
  consumed_at: string
  quantity: string
  unit_label: string
  note: string
  food: number | null
  snapshot_name: string
  snapshot_brand: string
  snapshot_source: string
  snapshot_reference_amount: string
  snapshot_reference_unit: UnitType
  /** Calculé côté serveur : le frontend ne refait jamais la multiplication. */
  computed: NutritionValues
}

export interface MealSection {
  meal_type: MealType
  entries: DiaryEntry[]
  totals: NutritionValues
  incomplete_nutrients: string[]
}

export interface DiaryGoals {
  date: string
  weekday: number
  daily_calories: string
  protein_g: string
  carbs_g: string
  fat_g: string
  fiber_g: string | null
}

export interface DiaryRemaining {
  daily_calories: string | null
  protein_g: string | null
  carbs_g: string | null
  fat_g: string | null
  fiber_g: string | null
}

/** Journée complète, renvoyée en un appel (spec 04 §4). */
export interface DiaryDay {
  date: string
  notes: string
  goals: DiaryGoals | null
  totals: NutritionValues
  /** Nutriments dont au moins une entrée n'était pas renseignée. */
  incomplete_nutrients: string[]
  remaining: DiaryRemaining | null
  meals: MealSection[]
}
