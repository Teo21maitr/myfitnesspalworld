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
