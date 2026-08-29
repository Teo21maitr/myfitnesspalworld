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

export type ShoppingItemSource = 'manual' | 'recipe' | 'meal_plan' | 'diary'

export interface ShoppingListItem {
  id: number
  name: string
  /** Nul pour un article ajouté à la main ou dont l'aliment a disparu. */
  food: number | null
  /** Nulle quand on ne la connaît pas : « du sel » est un article valable. */
  quantity: string | null
  unit_label: string | null
  is_checked: boolean
  sort_order: number
  source_type: ShoppingItemSource
}

export interface ShoppingList {
  id: number
  name: string
  visibility: Visibility
  items: ShoppingListItem[]
  is_editable: boolean
  created_at: string
  updated_at: string
}

/** Ce qu'un autre compte peut savoir d'un utilisateur (spec 01 §1). */
export interface UserSummary {
  id: number
  username: string
  first_name: string
  last_name: string
}

export type FriendRequestStatus = 'pending' | 'accepted' | 'rejected' | 'cancelled'

export interface FriendRequest {
  id: number
  from_user: UserSummary
  to_user: UserSummary
  status: FriendRequestStatus
  /** « reçue » ou « envoyée », du point de vue de l'appelant. */
  direction: 'received' | 'sent'
  created_at: string
}

/** Ressources partageables (spec 01 §18). Les photos n'en font jamais partie. */
export type ShareResourceType =
  'food' | 'recipe' | 'saved_meal' | 'shopping_list' | 'diary' | 'progress'

export type ShareVisibility = 'specific_user' | 'app_users'

export interface SharePermission {
  id: number
  owner: UserSummary
  target_user: UserSummary | null
  resource_type: ShareResourceType
  /** Nul pour le journal et la progression, qui ne sont pas une ligne. */
  resource_id: number | null
  resource_name: string
  visibility: ShareVisibility
  created_at: string
}

/** Valeurs nutritionnelles d'une recette, **pour une portion** (spec 01 §14). */
export interface RecipeNutrition extends NutritionValues {
  net_carbs_g: string | null
  /** Nutriments qu'au moins un ingrédient ne renseigne pas (spec 01 §8). */
  incomplete_nutrients: string[]
}

export interface RecipeIngredient {
  id: number
  /** Nul si l'aliment a disparu ; `food_name` reste lisible. */
  food: number | null
  food_name: string
  quantity: string
  unit_label: string
  sort_order: number
}

export interface RecipeListItem {
  id: number
  name: string
  description: string
  servings: string
  visibility: Visibility
  is_favorite: boolean
  nutrition: RecipeNutrition | null
  ingredient_count: number
  is_editable: boolean
  created_at: string
  updated_at: string
}

export interface RecipeDetail extends RecipeListItem {
  instructions: string
  ingredients: RecipeIngredient[]
}

export type SavedMealItemType = 'food' | 'recipe'

export interface SavedMealItem {
  id: number
  item_type: SavedMealItemType
  food: number | null
  recipe: number | null
  item_name: string
  quantity: string
  unit_label: string
  sort_order: number
}

export interface SavedMeal {
  id: number
  name: string
  description: string
  visibility: Visibility
  items: SavedMealItem[]
  is_editable: boolean
  created_at: string
  updated_at: string
}

/** Mensurations d'une date. Chaque mesure est facultative (spec 01 §19). */
export interface BodyMeasurementEntry {
  id: number
  date: string
  waist_cm: string | null
  hips_cm: string | null
  chest_cm: string | null
  arm_cm: string | null
  thigh_cm: string | null
  body_fat_percent: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

/** Métriques traçables par `GET /progress/charts/` (spec 04 §14). */
export type ChartMetric = 'weight' | 'waist' | 'hips' | 'chest' | 'arm' | 'thigh' | 'body_fat'

export interface ChartPoint {
  date: string
  value: string
  /** Moyenne des mesures des sept derniers jours calendaires. */
  moving_average: string
}

export interface ChartSeries {
  metric: ChartMetric
  unit: string
  from: string
  to: string
  points: ChartPoint[]
  target: string | null
  trend_per_week: string | null
}

/** Réponse de `GET /profile/settings/`. */
export interface SearchLanguage {
  code: string
  label: string
}

export interface UserSettings {
  language: string
  theme_mode: ThemeMode
  date_format: string
  /** Langues interrogées lors d'une recherche de produits de marque (spec 11 §3). */
  food_search_languages: string[]
  /** Catalogue servi par le serveur : une liste tenue à deux endroits diverge. */
  available_food_search_languages: SearchLanguage[]
}

export interface DetailResponse {
  detail: string
}

export type FoodSource = 'ciqual' | 'off' | 'user' | 'generated'

/** Trois portées de partage, communes aux aliments, recettes et repas (spec 01 §18). */
export type Visibility = 'private' | 'specific_users' | 'app_users'

export type FoodVisibility = Visibility

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

/** Poids courant et chemin parcouru (spec 06 §5). */
export interface WeightSummary {
  latest_kg: string | null
  latest_date: string | null
  start_kg: string | null
  change_kg: string | null
  target_kg: string | null
  /** Part du chemin parcouru vers le poids cible, en pourcentage. */
  progress_percent: string | null
}

/**
 * Tableau de bord : la journée, plus le poids (spec 04 §16).
 *
 * Le bloc « notifications importantes » de la spec est absent tant que le
 * modèle correspondant n'existe pas côté serveur.
 */
export interface Dashboard extends DiaryDay {
  weight: WeightSummary
}

/** Disponibilité de l'IA (spec 07 §11). */
export interface AIStatus {
  enabled: boolean
}

/** État d'un traitement long (spec 04 §9). */
export type TaskStatus = 'pending' | 'processing' | 'success' | 'failed'

export interface AsyncTask<TResult = unknown> {
  id: string
  task_type: 'meal_scan' | 'label_scan' | 'meal_planner'
  status: TaskStatus
  progress: number
  result: TResult | null
  /** Message destiné à l'utilisateur, jamais une trace technique. */
  error: string | null
  created_at: string
}

/**
 * Aliment de la base proposé pour un libellé détecté (spec 07 §5).
 *
 * Ses valeurs nutritionnelles viennent de la fiche : le modèle qui a regardé
 * la photo n'en propose aucune.
 */
export interface MealScanCandidate {
  id: number
  name: string
  brand: string
  source: FoodSource
  source_label: string
  reference_amount: string
  reference_unit: UnitType
  nutrition: {
    energy_kcal: string | null
    protein_g: string | null
    carbohydrates_g: string | null
    fat_g: string | null
  }
  available_units: string[]
}

/** Un aliment détecté sur la photo, à confirmer par l'utilisateur. */
export interface MealScanSuggestion {
  label: string
  estimated_quantity: string
  unit: string
  /** Confiance du modèle, entre 0 et 1. */
  confidence: number
  alternatives: string[]
  /** Vide lorsque aucun aliment de la base ne correspond au libellé. */
  candidates: MealScanCandidate[]
}

export interface MealScanResult {
  suggestions: MealScanSuggestion[]
}

export type MealScanTask = AsyncTask<MealScanResult>

/**
 * Nutriments qu'une étiquette européenne déclare et que le modèle sait porter.
 *
 * Les acides gras saturés, pourtant obligatoires sur l'étiquette, n'ont pas de
 * colonne : la spec 01 §4 ne les prévoit pas.
 */
export const LABEL_NUTRIENTS = [
  'energy_kcal',
  'protein_g',
  'carbohydrates_g',
  'sugars_g',
  'fat_g',
  'fiber_g',
  'salt_g',
  'sodium_mg',
] as const

export type LabelNutrient = (typeof LABEL_NUTRIENTS)[number]

/** Brouillon d'aliment lu sur une étiquette, à vérifier avant enregistrement. */
export interface LabelDraft {
  name: string
  brand: string
  barcode: string
  reference_amount: string
  reference_unit: UnitType
  /** `null` pour ce que la photo n'a pas donné — jamais 0 (spec 01 §8). */
  nutrition: Record<LabelNutrient, string | null>
}

export interface LabelScanResult {
  /** Colonne lue. `unknown` : aucune valeur n'a pu être reprise. */
  basis: '100g' | '100ml' | 'unknown'
  draft: LabelDraft
  /** Nutriments que la photo n'a pas donnés, nommés plutôt que devinés. */
  unreadable: LabelNutrient[]
}

export type LabelScanTask = AsyncTask<LabelScanResult>

/** Nature d'un élément planifié (spec 03 §7). */
export type PlanEntryType = 'food' | 'recipe' | 'saved_meal'

/** Les quatre valeurs affichées d'un élément ou d'une journée. */
export type MacroValues = Record<
  'energy_kcal' | 'protein_g' | 'carbohydrates_g' | 'fat_g',
  string | null
>

export interface PlanEntry {
  id: number
  meal_type: number
  entry_type: PlanEntryType
  food: number | null
  recipe: number | null
  quantity: string
  unit_label: string
  sort_order: number
  generated_by_ai: boolean
  label: string
  values: MacroValues
}

export interface PlanDay {
  id: number
  date: string
  entries: PlanEntry[]
  totals: MacroValues
  incomplete_nutrients: string[]
  targets: Record<string, string> | null
  /** Écart en pourcentage, mesuré sur les fiches de la base. */
  deviations: Record<string, number>
  /** Calculé côté serveur : recopier les seuils ici les ferait diverger. */
  within_tolerance: boolean
}

export interface MealPlanListItem {
  id: number
  name: string
  start_date: string
  end_date: string
  generated_by_ai: boolean
  days_count: number
  created_at: string
}

export interface MealPlan extends MealPlanListItem {
  notes: string
  days: PlanDay[]
  /** Recettes proposées qu'aucun ingrédient ne rendait enregistrables. */
  skipped_recipes?: string[]
}

/**
 * Recette inédite proposée par le modèle.
 *
 * Elle n'existe pas encore : c'est l'enregistrement du plan qui la crée
 * (spec 07 §8).
 */
export interface ProposedRecipe {
  name: string
  servings: string
  instructions: string
  ingredients: { food_id: number; label: string; quantity: string; unit_label: string }[]
}

export interface ProposalItem {
  entry_type: PlanEntryType
  label: string
  quantity: string
  unit_label: string
  values: MacroValues
  food?: MealScanCandidate
  recipe_id?: number
  new_recipe?: ProposedRecipe
}

export interface ProposalMeal {
  meal: string
  meal_type_id: number | null
  items: ProposalItem[]
}

export interface ProposalDay {
  date: string
  targets: Record<string, string>
  totals: MacroValues
  deviations: Record<string, number>
  /** Faux quand la journée sort des tolérances après trois essais. */
  within_tolerance: boolean
  attempts: number
  /** Libellés que la base n'a pas retrouvés, nommés plutôt qu'inventés. */
  unmatched: string[]
  meals: ProposalMeal[]
}

/** Proposition de plan : rien n'est encore enregistré. */
export interface PlanProposal {
  name: string
  start_date: string
  end_date: string
  days: ProposalDay[]
  warnings: string[]
}

export type MealPlanTask = AsyncTask<PlanProposal>

/**
 * Contribution d'un aliment à un nutriment sur une période (spec 01 §21).
 *
 * `share` est une part du total **connu** : quand l'analyse est partielle,
 * c'est un minorant, jamais un pourcentage exact.
 */
export interface AnalysisSource {
  name: string
  total: string
  entries: number
  share: number
}

/** Réponse de `GET /analysis/food/`. */
export interface NutrientAnalysis {
  nutrient: string
  label: string
  from: string
  to: string
  /** Nul quand aucune entrée ne renseigne ce nutriment. */
  total: string | null
  sources: AnalysisSource[]
  /** Entrées qui ne renseignent pas ce nutriment. Elles ne valent pas zéro. */
  unknown_entries: number
  /** Dénominateur des moyennes : les journées qui portent une entrée. */
  logged_days: number
  is_partial: boolean
}

/** Une journée **tenue** d'un rapport. */
export interface ReportDay {
  date: string
  entries: number
  target_calories: string | null
  weight_kg: string | null
  totals: Record<string, string | null>
  incomplete_nutrients: string[]
}

/** Réponse de `GET /reports/summary/` et `GET /analysis/weekly/`. */
export interface PeriodReport {
  from: string
  to: string
  days: ReportDay[]
  /** Moyennes sur les journées tenues, `null` quand rien n'a été mesuré. */
  averages: Record<string, string | null>
  adherence: { days_measured: number; days_within_goal: number }
  top_foods: AnalysisSource[]
  logged_days: number
  calendar_days: number
  weight_change: string | null
  weight: {
    points: ChartPoint[]
    target: string | null
    trend_per_week: string | null
  }
}
