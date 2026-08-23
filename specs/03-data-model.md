# 03 — Modèle de données

Les noms exacts peuvent évoluer légèrement pendant l'implémentation, mais les responsabilités et relations doivent rester compatibles avec ce document.

## 1. Accounts

### RegistrationRequest

- id
- first_name
- last_name
- username
- email nullable
- password_hash ou mécanisme de création sécurisé
- created_at
- status interne si nécessaire

Après acceptation, créer le `User`, puis supprimer la demande.

### User

Modèle Django custom dès la première migration.

- id
- username
- normalized_username
- email nullable
- first_name
- last_name
- status: `PENDING | ACTIVE | SUSPENDED`
- is_staff
- is_superuser
- password
- created_at
- updated_at
- last_login

Le statut `REJECTED` n'a pas besoin d'être persisté sur User puisque la demande refusée est supprimée.

Contrainte : username unique insensible à la casse.

### UserProfile

- user FK/OneToOne
- birth_date
- sex_for_calculation
- height_cm
- activity_level
- goal_type
- goal_rate
- target_weight_kg
- onboarding_completed
- created_at
- updated_at

### UserSettings

- user OneToOne
- language = `fr`
- theme_mode: `light | dark | system`
- date_format
- dashboard_config JSON
- privacy_config JSON
- created_at
- updated_at

## 2. Nutrition goals

### NutritionGoal

- id
- user
- daily_calories Decimal
- protein_g Decimal
- carbs_g Decimal
- fat_g Decimal
- fiber_g nullable
- macro_mode: `percentage | grams`
- calories_source: `calculated | manual`
- macros_source: `calculated | manual`
- start_date
- end_date nullable
- created_at

### NutritionGoalDayOverride

- id
- nutrition_goal
- weekday 0..6
- daily_calories nullable
- protein_g nullable
- carbs_g nullable
- fat_g nullable
- other nutrients nullable
- enabled

### MealNutritionGoal

- id
- nutrition_goal
- meal_type
- calories nullable
- protein_g nullable
- carbs_g nullable
- fat_g nullable

## 3. Foods

### Food

- id
- name
- brand nullable
- barcode nullable
- source: `ciqual | off | user | generated`
- visibility: `private | specific_users | app_users`
- owner nullable
- external_id nullable
- default_unit_type: `g | ml | unit`
- reference_amount = 100
- reference_unit: `g | ml`
- is_verified
- is_active
- search_text
- external_updated_at nullable
- cache_refreshed_at nullable
- created_at
- updated_at
- deleted_at nullable

### FoodNutrition

OneToOne Food.

- energy_kcal
- protein_g
- carbohydrates_g
- fat_g
- fiber_g nullable
- sugars_g nullable
- sodium_mg nullable
- salt_g nullable
- cholesterol_mg nullable
- potassium_mg nullable
- calcium_mg nullable
- iron_mg nullable
- magnesium_mg nullable
- vitamin_a nullable
- vitamin_b6 nullable
- vitamin_b12 nullable
- vitamin_c nullable
- vitamin_d nullable
- vitamin_e nullable
- vitamin_k nullable

Tous les champs numériques persistés utilisent `DecimalField`.

### FoodPortion

- id
- food
- owner nullable
- name
- gram_equivalent nullable
- milliliter_equivalent nullable
- unit_equivalent nullable
- is_default
- sort_order

Si `owner != null`, portion privée à cet utilisateur.

### UserFoodFavorite

- user
- food
- created_at

Unique `(user, food)`.

### UserFoodHistory

- user
- food
- last_used_at
- use_count

Unique `(user, food)`.

## 4. Diary

### DiaryDay

- id
- user
- date
- notes nullable
- created_at
- updated_at

Unique `(user, date)`.

### MealType

- id
- user nullable
- system_key nullable
- name
- slug
- sort_order
- is_default
- is_active

Les quatre types par défaut sont désactivables mais pas supprimés physiquement.

### DiaryEntry

- id
- diary_day
- meal_type
- entry_type: `food | recipe | quick_add`
- consumed_at
- quantity Decimal
- unit_label
- note nullable
- food nullable
- recipe nullable
- saved_meal nullable si utile à la traçabilité
- snapshot_name
- snapshot_brand nullable
- snapshot_source
- snapshot_reference_amount
- snapshot_reference_unit
- snapshot_energy_kcal
- snapshot_protein_g
- snapshot_carbohydrates_g
- snapshot_fat_g
- snapshot_fiber_g nullable
- snapshot_sugars_g nullable
- snapshot_sodium_mg nullable
- snapshot_salt_g nullable
- autres snapshots micronutriments
- created_at
- updated_at

Les snapshots sont les données historiques de vérité.

## 5. Saved meals

### SavedMeal

- id
- owner
- name
- description nullable
- visibility
- created_at
- updated_at
- deleted_at nullable

### SavedMealItem

- id
- saved_meal
- item_type: `food | recipe`
- food nullable
- recipe nullable
- quantity Decimal
- unit_label
- sort_order

## 6. Recipes

### Recipe

- id
- owner
- name
- description nullable
- instructions text
- servings Decimal
- visibility
- is_favorite
- cached_energy_kcal
- cached_protein_g
- cached_carbs_g
- cached_fat_g
- autres caches nutritionnels
- created_at
- updated_at
- deleted_at nullable

### RecipeIngredient

- id
- recipe
- food
- quantity Decimal
- unit_label
- sort_order

## 7. Planning

### MealPlan

- id
- owner
- name
- start_date
- end_date
- generated_by_ai
- notes nullable
- created_at
- updated_at

### MealPlanDay

- id
- meal_plan
- date

Unique `(meal_plan, date)`.

### MealPlanEntry

- id
- meal_plan_day
- meal_type
- entry_type: `food | recipe | saved_meal`
- food nullable
- recipe nullable
- saved_meal nullable
- quantity Decimal
- unit_label
- sort_order
- generated_by_ai

## 8. Shopping

### ShoppingList

- id
- owner
- name
- visibility
- created_at
- updated_at

### ShoppingListItem

- id
- shopping_list
- name
- food nullable
- quantity Decimal nullable
- unit_label nullable
- is_checked
- sort_order
- source_type: `manual | recipe | meal_plan | diary`

## 9. Social

### FriendRequest

- id
- from_user
- to_user
- status: `pending | accepted | rejected | cancelled`
- created_at
- updated_at

### Friendship

- id
- user_1
- user_2
- created_at

Contrainte canonique : toujours stocker le plus petit id en `user_1` pour éviter les doublons.

### SharePermission

- id
- owner
- target_user nullable
- resource_type
- resource_id
- visibility_type: `specific_user | app_users`
- created_at

Le backend valide strictement le type et l'ownership de la ressource.

## 10. Progress

### WeightEntry

- id
- user
- date
- weight_kg Decimal
- notes nullable
- created_at
- updated_at

Unique `(user, date)`.

### BodyMeasurementEntry

- id
- user
- date
- waist_cm nullable
- hips_cm nullable
- chest_cm nullable
- arm_cm nullable
- thigh_cm nullable
- body_fat_percent nullable
- notes nullable
- created_at
- updated_at

Unique `(user, date)`.

### ProgressPhotoGroup

- id
- user
- date
- weight_kg_snapshot nullable
- notes nullable
- created_at
- updated_at

### ProgressPhoto

- id
- group
- photo_type: `front | side | back | other`
- storage_key
- mime_type
- size_bytes
- created_at

## 11. Notifications

### Notification

- id
- user
- type
- title
- message
- is_read
- link nullable
- created_at

### NotificationPreference

- id
- user
- event_type
- in_app_enabled
- push_enabled
- email_enabled

Unique `(user, event_type)`.

### Reminder

- id
- user
- type
- time
- days_of_week
- enabled

Un seul rappel actif par type et utilisateur.

### EmailLog

- id
- user nullable
- email_type
- recipient
- status
- provider_response_summary nullable
- created_at

## 12. AI

### AITaskLog

- id
- user
- task_type: `meal_scan | voice_log | meal_planner | recipe_generation`
- status
- provider
- model
- input_summary nullable
- output_summary nullable
- error_message nullable
- cost_estimate nullable
- created_at
- finished_at nullable

Ne jamais stocker photo/audio brut permanent dans cette table.

### AsyncTask

Si Celery backend ne fournit pas une couche suffisante pour l'API, créer une table applicative :

- id UUID
- user
- task_type
- status
- progress
- result JSON nullable
- error nullable
- created_at
- updated_at
- expires_at nullable

## 13. Configuration

### AppSetting

- key unique
- value JSON
- description
- updated_at

Exemples :

- `meal_scan_enabled`
- `voice_logging_enabled`
- `planner_enabled`
- `max_upload_size_mb`
- `ai_enabled`
